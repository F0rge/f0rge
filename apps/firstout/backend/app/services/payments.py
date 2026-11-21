from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.bill import BillCRUD
from app.crud.journal import JournalCRUD
from app.crud.payment import PaymentCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.bill import BillApprovalStatus
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.journal import JournalDocumentType
from app.models.payment import Payment, PaymentDirection
from app.schemas.page import Page, PageParams
from app.schemas.payment import (
    PaymentCreate,
    PaymentOpenDocument,
    PaymentResponse,
    PaymentSummary,
)
from app.services.books_events import BooksEventService
from app.services.chart_of_accounts import (
    CODE_AP,
    CODE_AR,
    CODE_BANK,
    CODE_FX,
    LedgerPostingService,
)
from app.services.packing_sheet import convert_bill_to_zar
from app.services.books_periods import assert_date_postable
from app.services.settings import SettingsService
from app.services.payment_pdf import build_payment_receipt_pdf
from app.services.settlement import (
    assert_payment_cents,
    booked_portion,
    cents,
    overpayment_message,
)
from app.services.suppliers import SupplierService
from app.services.archive_documents import assert_operational_document, bill_display_number
from app.services.journals import JournalService
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = PaymentCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.bill_crud = BillCRUD(db)
        self.posting = LedgerPostingService(db)
        self.events = BooksEventService(db)

    async def list(
        self,
        params: PageParams,
        *,
        invoice_id: Optional[uuid.UUID] = None,
        bill_id: Optional[uuid.UUID] = None,
    ) -> Page[PaymentResponse]:
        payments, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
            invoice_id=invoice_id,
            bill_id=bill_id,
        )
        return Page(
            items=[self._to_response(payment) for payment in payments],
            total=total,
        )

    async def create(
        self, data: PaymentCreate, user_id: Optional[uuid.UUID] = None
    ) -> PaymentResponse:
        if data.direction == "in":
            return await self._create_payment_in(data, user_id)
        return await self._create_payment_out(data, user_id)

    async def _create_payment_in(
        self,
        data: PaymentCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> PaymentResponse:
        async with unit_of_work(self.db):
            payment = await self.stage_payment_in(data, user_id)
            await self.crud.commit_refresh(payment)

        reloaded = await self.crud.get_by_id(payment.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def stage_payment_in(
        self,
        data: PaymentCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Payment:
        """Validate and flush a payment in without committing, so a caller can make it
        part of a larger transaction (an invoice issued already paid)."""
        if data.invoice_id is None:
            raise ValidationError("invoice_id is required for payment in")
        if data.bill_id is not None:
            raise ValidationError("bill_id must not be set for payment in")

        currency = SupplierService.normalize_currency(data.currency)
        if currency != "ZAR":
            raise ValidationError("Invoice payments must be in ZAR")

        # Locked until commit so a concurrent payment or void cannot lose this update.
        invoice = await self.invoice_crud.get_by_id(data.invoice_id, for_update=True)
        if invoice is None:
            raise NotFoundError("Invoice not found")
        assert_operational_document(invoice)

        amount = assert_payment_cents(data.amount)
        remaining = cents(invoice.total_inc_vat - invoice.amount_paid)
        if remaining <= 0:
            raise ValidationError("Invoice is already fully paid")
        if amount > remaining:
            raise ValidationError(overpayment_message(remaining, "ZAR", invoice.invoice_number))

        await assert_date_postable(self.db, data.paid_on)

        payment = Payment(
            payment_number="",
            direction=PaymentDirection.IN,
            invoice_id=invoice.id,
            amount=amount,
            currency=currency,
            fx_to_zar=Decimal("1"),
            amount_zar=amount,
            fx_gain_loss_zar=Decimal(0),
            paid_on=data.paid_on,
            tender=data.tender,
            reference=data.reference,
        )

        payment.payment_number = await self.crud.get_next_payment_number()
        await self.crud.add_and_flush(payment)
        await self.posting.post(
            JournalDocumentType.PAYMENT,
            payment.id,
            f"Payment {payment.payment_number} received",
            [
                (CODE_BANK, amount, Decimal(0)),
                (CODE_AR, Decimal(0), amount),
            ],
            entry_date=payment.paid_on,
        )
        invoice.amount_paid = cents(invoice.amount_paid + amount)
        await self.events.record(
            BooksDocumentType.PAYMENT,
            payment.id,
            BooksEventAction.CREATED,
            actor_user_id=user_id,
        )
        return payment

    async def _create_payment_out(
        self,
        data: PaymentCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> PaymentResponse:
        if data.bill_id is None:
            raise ValidationError("bill_id is required for payment out")
        if data.invoice_id is not None:
            raise ValidationError("invoice_id must not be set for payment out")

        bill = await self.bill_crud.get_by_id(data.bill_id, for_update=True)
        if bill is None:
            raise NotFoundError("Bill not found")
        assert_operational_document(bill)
        if bill.approval_status != BillApprovalStatus.APPROVED:
            raise ValidationError("Approve this bill before recording a payment against it.")
        if bill.archived_at is not None:
            raise ValidationError("Restore this bill before recording a payment against it.")

        currency = SupplierService.normalize_currency(data.currency)
        if currency != bill.currency:
            raise ValidationError("Payment currency must match bill currency")

        amount = assert_payment_cents(data.amount)
        remaining_foreign = cents(bill.amount_foreign - bill.amount_paid_foreign)
        if remaining_foreign <= 0:
            raise ValidationError("Bill is already fully paid")
        if amount > remaining_foreign:
            raise ValidationError(
                overpayment_message(remaining_foreign, currency, bill.bill_number)
            )

        fx_to_zar = self._resolve_fx(currency, data.fx_to_zar)
        cleared_zar = booked_portion(
            amount=amount,
            amount_foreign=bill.amount_foreign,
            amount_zar=bill.amount_zar,
            amount_paid_foreign=bill.amount_paid_foreign,
            amount_paid_zar=bill.amount_paid_zar,
        )
        if cleared_zar <= 0:
            raise ValidationError("Payment is too small to reduce this bill.")
        settlement_zar = cents(convert_bill_to_zar(amount, currency, fx_to_zar))
        if settlement_zar <= 0:
            raise ValidationError("Payment is too small to reduce this bill.")
        diff = settlement_zar - cleared_zar
        fx_gain_loss = cleared_zar - settlement_zar

        journal_lines: list[tuple[str, Decimal, Decimal]] = [
            (CODE_AP, cleared_zar, Decimal(0)),
            (CODE_BANK, Decimal(0), settlement_zar),
        ]
        if diff > 0:
            journal_lines.append((CODE_FX, diff, Decimal(0)))
        elif diff < 0:
            journal_lines.append((CODE_FX, Decimal(0), abs(diff)))

        await assert_date_postable(self.db, data.paid_on)

        payment = Payment(
            payment_number="",
            direction=PaymentDirection.OUT,
            bill_id=bill.id,
            amount=amount,
            currency=currency,
            fx_to_zar=fx_to_zar,
            amount_zar=settlement_zar,
            fx_gain_loss_zar=fx_gain_loss,
            paid_on=data.paid_on,
            tender=data.tender,
            reference=data.reference,
        )

        async with unit_of_work(self.db):
            payment.payment_number = await self.crud.get_next_payment_number()
            await self.crud.add_and_flush(payment)
            await self.posting.post(
                JournalDocumentType.PAYMENT,
                payment.id,
                f"Payment {payment.payment_number} sent",
                journal_lines,
                entry_date=payment.paid_on,
            )
            bill.amount_paid_zar = cents(bill.amount_paid_zar + cleared_zar)
            bill.amount_paid_foreign = cents(bill.amount_paid_foreign + amount)
            await self.events.record(
                BooksDocumentType.PAYMENT,
                payment.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
            )
            await self.crud.commit_refresh(payment)

        reloaded = await self.crud.get_by_id(payment.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def void(
        self, payment_id: uuid.UUID, reason: str, user_id: Optional[uuid.UUID] = None
    ) -> PaymentResponse:
        """Keep the payment on record, reverse its ledger effect and reopen the balance."""
        payment = await self.crud.get_by_id(payment_id, for_update=True)
        if payment is None:
            raise NotFoundError("Payment not found")
        if payment.voided_at is not None:
            raise ValidationError("This payment is already voided")
        if payment.is_reconciled:
            raise ValidationError("A reconciled payment cannot be voided")
        # Lock and refresh the document's paid totals before recalculating them.
        if payment.invoice_id is not None:
            await self.invoice_crud.get_by_id(payment.invoice_id, for_update=True)
        elif payment.bill_id is not None:
            await self.bill_crud.get_by_id(payment.bill_id, for_update=True)
        assert_operational_document(payment.invoice or payment.bill)
        entries = await JournalCRUD(self.db).list_posted_for_document(
            JournalDocumentType.PAYMENT, payment.id
        )
        for entry in entries:
            await assert_date_postable(self.db, entry.entry_date)

        journals = JournalService(self.db)
        async with unit_of_work(self.db):
            for entry in entries:
                await journals.stage_reversal(
                    entry,
                    memo=f"Void of payment {payment.payment_number}",
                    document_type=JournalDocumentType.PAYMENT,
                    document_id=payment.id,
                )
            if payment.invoice is not None:
                payment.invoice.amount_paid = cents(payment.invoice.amount_paid - payment.amount)
            elif payment.bill is not None:
                # Recording cleared (settlement ZAR + FX gain/loss) off the bill; undo that.
                cleared_zar = payment.amount_zar + payment.fx_gain_loss_zar
                payment.bill.amount_paid_zar = cents(payment.bill.amount_paid_zar - cleared_zar)
                payment.bill.amount_paid_foreign = cents(
                    payment.bill.amount_paid_foreign - payment.amount
                )
            payment.voided_at = datetime.datetime.now(datetime.timezone.utc)
            payment.voided_by_id = user_id
            payment.void_reason = reason
            await self.events.record(
                BooksDocumentType.PAYMENT,
                payment.id,
                BooksEventAction.VOIDED,
                actor_user_id=user_id,
                note=reason,
            )

        reloaded = await self.crud.get_by_id(payment.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def list_all(self) -> list[PaymentResponse]:
        return [self._to_response(payment) for payment in await self.crud.list_all()]

    async def open_documents(self, direction: str) -> list[PaymentOpenDocument]:
        # Imported lazily: bank imports record their payments through this service.
        from app.services.bank_imports import BankImportService

        kind = "invoice" if direction == "in" else "bill"
        documents = [
            document
            for document in await BankImportService(self.db).open_documents()
            if document.kind == kind
        ]
        documents.sort(key=lambda document: (document.issue_date, document.number))
        return [PaymentOpenDocument.model_validate(document) for document in documents]

    async def summary(self) -> PaymentSummary:
        start = datetime.date.today().replace(day=1)
        end = (start + datetime.timedelta(days=32)).replace(day=1)
        month, unreconciled_count, unreconciled_net = await self.crud.summary(start, end)
        received = month.get(PaymentDirection.IN, (0, Decimal(0)))
        paid = month.get(PaymentDirection.OUT, (0, Decimal(0)))
        return PaymentSummary(
            received_this_month_count=received[0],
            received_this_month_zar=cents(received[1]),
            paid_this_month_count=paid[0],
            paid_this_month_zar=cents(paid[1]),
            unreconciled_count=unreconciled_count,
            unreconciled_net_zar=cents(unreconciled_net),
        )

    async def serve_pdf(self, payment_id: uuid.UUID) -> Response:
        payment = await self.crud.get_by_id(payment_id)
        if payment is None:
            raise NotFoundError("Payment not found")
        direction_label = "Received" if payment.direction == PaymentDirection.IN else "Paid"
        linked_document: Optional[str] = None
        if payment.invoice is not None:
            linked_document = f"Invoice: {payment.invoice.invoice_number}"
        elif payment.bill is not None:
            linked_document = f"Bill: {payment.bill.bill_number}"
        pdf_bytes = build_payment_receipt_pdf(
            payment_number=payment.payment_number,
            direction_label=direction_label,
            paid_on=payment.paid_on.isoformat(),
            amount=f"{payment.amount:.2f}",
            currency=payment.currency,
            amount_zar=f"{payment.amount_zar:.2f}",
            tender=payment.tender,
            linked_document=linked_document,
            seller=await SettingsService(self.db).build_seller_details(),
        )
        return Response(content=pdf_bytes, media_type="application/pdf")

    async def _team_settings(self):
        team = await TeamCRUD(self.db).get_first()
        if team is None:
            raise NotFoundError("Team not found")
        return await TeamSettingsCRUD(self.db).get_or_create_for_team(team.id)

    @staticmethod
    def _resolve_fx(currency: str, fx_to_zar: Optional[Decimal]) -> Decimal:
        if currency == "ZAR":
            return Decimal("1")
        if fx_to_zar is None or fx_to_zar <= 0:
            raise ValidationError("fx_to_zar is required and must be positive for foreign currency")
        return fx_to_zar

    @staticmethod
    def _to_response(payment: Payment) -> PaymentResponse:
        party_name = document_number = None
        if payment.invoice is not None:
            party_name = payment.invoice.customer.name
            document_number = payment.invoice.invoice_number
        elif payment.bill is not None:
            party_name = payment.bill.supplier.name
            document_number = bill_display_number(payment.bill)
        return PaymentResponse(
            id=payment.id,
            payment_number=payment.payment_number,
            direction=payment.direction.value,
            invoice_id=payment.invoice_id,
            bill_id=payment.bill_id,
            amount=payment.amount,
            currency=payment.currency,
            fx_to_zar=payment.fx_to_zar,
            amount_zar=payment.amount_zar,
            fx_gain_loss_zar=payment.fx_gain_loss_zar,
            paid_on=payment.paid_on,
            tender=payment.tender,
            reference=payment.reference,
            party_name=party_name,
            document_number=document_number,
            is_reconciled=payment.is_reconciled,
            reconciled_at=payment.reconciled_at,
            is_voided=payment.voided_at is not None,
            voided_at=payment.voided_at,
            void_reason=payment.void_reason,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )
