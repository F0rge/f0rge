from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.tax_invoice import TaxInvoiceCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.customer import Customer
from app.models.journal import JournalDocumentType
from app.models.sku import Sku
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.services.books_events import BooksEventService
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import CODE_AR, CODE_DEPOSITS, CODE_VAT, LedgerPostingService
from app.services.payment_terms import compute_due_date
from f0rge_core.exceptions import NotFoundError


@dataclass(frozen=True)
class Deposits:
    """Customer deposits already held in 2300, applied against the new invoice's AR."""

    source_id: uuid.UUID
    memo: str
    amount: Decimal


class TaxInvoiceIssue:
    """Tax invoice issue (CONTEXT.md): the moment a tax invoice gets its number and issue date.

    Every sale document that bills a customer (till sale, layby completion, sales order
    remainder, books invoice) issues through here. The caller prices the lines; this module
    numbers the invoice, snapshots its due date, posts Dr AR / Cr sales / Cr VAT, applies
    deposits already taken, and records the books event. Call it inside the caller's
    ``unit_of_work``: nothing here commits, so the caller's own postings (payment, cost of
    goods, stock, document status) land in the same transaction.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TaxInvoiceCRUD(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)

    async def issue(
        self,
        *,
        customer: Customer,
        issue_date: datetime.date,
        lines: list[InvoiceLine],
        vat_rate: Decimal,
        prices_include_vat: bool,
        memo: str,
        actor_user_id: Optional[uuid.UUID],
        due_date: Optional[datetime.date] = None,
        deposits: Optional[Deposits] = None,
        sales_staff_id: Optional[uuid.UUID] = None,
        on_account: bool = False,
        note_printed: Optional[str] = None,
        note_internal: Optional[str] = None,
        source: str = "manual",
        event_note: Optional[str] = None,
    ) -> TaxInvoice:
        """Issue ``lines`` as a numbered, posted tax invoice.

        ``vat_rate`` is the rate the caller priced ``lines`` at; the invoice keeps it.

        ``memo`` labels the sales journal ("Till tax invoice" → "Till tax invoice INV-0001").
        Raises ``ConflictError`` when the books period covering ``issue_date`` is locked.
        """
        if due_date is None:
            due_date = compute_due_date(issue_date, customer, await self._team_settings())

        subtotal = sum((line.ex_vat for line in lines), Decimal(0))
        vat_total = sum((line.vat_amount for line in lines), Decimal(0))
        total_inc = subtotal + vat_total
        invoice_number = await self.crud.get_next_invoice_number()
        invoice = TaxInvoice(
            invoice_number=invoice_number,
            customer_id=customer.id,
            issue_date=issue_date,
            due_date=due_date,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_total,
            total_inc_vat=total_inc,
            vat_rate=vat_rate,
            amount_paid=deposits.amount if deposits is not None else Decimal(0),
            prices_include_vat=prices_include_vat,
            on_account=on_account,
            note_printed=note_printed,
            note_internal=note_internal,
            sales_staff_id=sales_staff_id,
            source=source,
            lines=lines,
        )
        await self.crud.add_and_flush(invoice)

        sales_parts: list[tuple[str, Decimal, Decimal]] = []
        for line in lines:
            # A line without a SKU (free text, storefront delivery) posts to CODE_SALES.
            sku = await self.db.get(Sku, line.sku_id) if line.sku_id is not None else None
            sales_code = await self.category_posting.sales_code_for_sku(sku)
            sales_parts.append((sales_code, Decimal(0), line.ex_vat))
        await self.posting.post(
            JournalDocumentType.INVOICE,
            invoice.id,
            f"{memo} {invoice_number}",
            self.category_posting.collapse(
                [(CODE_AR, total_inc, Decimal(0)), *sales_parts, (CODE_VAT, Decimal(0), vat_total)]
            ),
            entry_date=issue_date,
        )
        if deposits is not None and deposits.amount > 0:
            await self.posting.post(
                JournalDocumentType.PAYMENT,
                deposits.source_id,
                deposits.memo,
                [
                    (CODE_DEPOSITS, deposits.amount, Decimal(0)),
                    (CODE_AR, Decimal(0), deposits.amount),
                ],
                entry_date=issue_date,
            )
        await BooksEventService(self.db).record(
            BooksDocumentType.INVOICE,
            invoice.id,
            BooksEventAction.CREATED,
            actor_user_id=actor_user_id,
            note=event_note,
        )
        return invoice

    async def _team_settings(self):
        team = await TeamCRUD(self.db).get_first()
        if team is None:
            raise NotFoundError("Team not found")
        # Read only: creating settings on first use commits, which would end the
        # caller's transaction. A missing row means the defaults it would be created with.
        return await TeamSettingsCRUD(self.db).get_by_team_id(team.id)
