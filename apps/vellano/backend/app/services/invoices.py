from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.sku import SkuCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.journal import JournalDocumentType
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.schemas.invoice import InvoiceCreate, InvoiceLineResponse, InvoiceResponse
from app.services.books_events import BooksEventService
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_VAT,
    LedgerPostingService,
)
from app.services.contacts import ContactService
from app.services.invoice_pdf import build_tax_invoice_pdf
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TaxInvoiceCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.contact_service = ContactService(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)
        self.events = BooksEventService(db)

    async def list(self) -> list[InvoiceResponse]:
        invoices = await self.crud.list_all()
        return [self._to_response(invoice) for invoice in invoices]

    async def get(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        invoice = await self.crud.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")
        return self._to_response(invoice)

    async def create(
        self, data: InvoiceCreate, user_id: Optional[uuid.UUID] = None
    ) -> InvoiceResponse:
        await self.contact_service.get_customer(data.customer_id)

        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        line_models: list[InvoiceLine] = []

        for index, line in enumerate(data.lines):
            ex_vat = (Decimal(line.qty) * line.unit_ex_vat).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            line_models.append(
                InvoiceLine(
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    ex_vat=ex_vat,
                    inc_vat=inc_vat,
                    vat_amount=line_vat,
                    sort_order=index,
                )
            )

        if subtotal <= 0:
            raise ValidationError("Invoice total must be positive")

        invoice_number = await self.crud.get_next_invoice_number()
        invoice = TaxInvoice(
            invoice_number=invoice_number,
            customer_id=data.customer_id,
            issue_date=data.issue_date,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_total,
            total_inc_vat=total_inc,
            amount_paid=Decimal(0),
            lines=line_models,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(invoice)
            sales_parts: list[tuple[str, Decimal, Decimal]] = []
            for line in line_models:
                sku = None
                if line.sku_id is not None:
                    sku = await self.sku_crud.get_by_id(line.sku_id)
                sales_code = await self.category_posting.sales_code_for_sku(sku)
                sales_parts.append((sales_code, Decimal(0), line.ex_vat))
            await self.posting.post(
                JournalDocumentType.INVOICE,
                invoice.id,
                f"Tax invoice {invoice_number}",
                self.category_posting.collapse(
                    [
                        (CODE_AR, total_inc, Decimal(0)),
                        *sales_parts,
                        (CODE_VAT, Decimal(0), vat_total),
                    ]
                ),
                entry_date=invoice.issue_date,
            )
            await self.events.record(
                BooksDocumentType.INVOICE,
                invoice.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
            )
            await self.crud.commit_refresh(invoice)

        reloaded = await self.crud.get_by_id(invoice.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def serve_pdf(self, invoice_id: uuid.UUID) -> Response:
        invoice = await self.crud.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")

        lines = []
        for line in invoice.lines:
            description = line.description
            if line.sku_id is not None:
                sku = await self.sku_crud.get_by_id(line.sku_id)
                if sku is not None and sku.carton_count > 1:
                    cartons = line.qty * sku.carton_count
                    description = f"{description} - Ships in {cartons} cartons"
            lines.append(
                (
                    description,
                    line.qty,
                    f"{line.unit_ex_vat:.2f}",
                    f"{line.ex_vat:.2f}",
                    f"{line.vat_amount:.2f}",
                    f"{line.inc_vat:.2f}",
                )
            )
        pdf_bytes = build_tax_invoice_pdf(
            invoice_number=invoice.invoice_number,
            issue_date=invoice.issue_date.isoformat(),
            customer_name=invoice.customer.name,
            customer_vat=invoice.customer.vat_number,
            customer_address=invoice.customer.billing_address,
            lines=lines,
            subtotal_ex_vat=f"{invoice.subtotal_ex_vat:.2f}",
            vat_amount=f"{invoice.vat_amount:.2f}",
            total_inc_vat=f"{invoice.total_inc_vat:.2f}",
        )
        return Response(content=pdf_bytes, media_type="application/pdf")

    @staticmethod
    def _to_response(invoice: TaxInvoice) -> InvoiceResponse:
        balance = invoice.total_inc_vat - invoice.amount_paid
        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.name,
            issue_date=invoice.issue_date,
            subtotal_ex_vat=invoice.subtotal_ex_vat,
            vat_amount=invoice.vat_amount,
            total_inc_vat=invoice.total_inc_vat,
            amount_paid=invoice.amount_paid,
            balance=balance,
            lines=[
                InvoiceLineResponse(
                    id=line.id,
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    ex_vat=line.ex_vat,
                    inc_vat=line.inc_vat,
                    vat_amount=line.vat_amount,
                    sort_order=line.sort_order,
                    sku_id=line.sku_id,
                )
                for line in invoice.lines
            ],
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )
