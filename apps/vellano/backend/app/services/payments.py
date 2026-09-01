from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.bill import BillCRUD
from app.crud.payment import PaymentCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.journal import JournalDocumentType
from app.models.payment import Payment, PaymentDirection
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.books_events import BooksEventService
from app.services.chart_of_accounts import (
    CODE_AP,
    CODE_AR,
    CODE_BANK,
    CODE_FX,
    LedgerPostingService,
)
from app.services.packing_sheet import convert_bill_to_zar
from app.services.payment_pdf import build_payment_receipt_pdf
from app.services.suppliers import SupplierService
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

    async def list(self) -> list[PaymentResponse]:
        payments = await self.crud.list_all()
        return [self._to_response(payment) for payment in payments]

    async def create(
        self, data: PaymentCreate, user_id: Optional[uuid.UUID] = None
    ) -> PaymentResponse:
        payment_number = await self.crud.get_next_payment_number()

        if data.direction == "in":
            return await self._create_payment_in(data, payment_number, user_id)
        return await self._create_payment_out(data, payment_number, user_id)

    async def _create_payment_in(
        self,
        data: PaymentCreate,
        payment_number: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> PaymentResponse:
        if data.invoice_id is None:
            raise ValidationError("invoice_id is required for payment in")
        if data.bill_id is not None:
            raise ValidationError("bill_id must not be set for payment in")

        currency = SupplierService.normalize_currency(data.currency)
        if currency != "ZAR":
            raise ValidationError("Invoice payments must be in ZAR")

        invoice = await self.invoice_crud.get_by_id(data.invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")

        remaining = invoice.total_inc_vat - invoice.amount_paid
        if remaining <= 0:
            raise ValidationError("Invoice is already fully paid")
        if data.amount != remaining:
            raise ValidationError("Payment amount must equal the remaining invoice balance")

        payment = Payment(
            payment_number=payment_number,
            direction=PaymentDirection.IN,
            invoice_id=invoice.id,
            amount=data.amount,
            currency=currency,
            fx_to_zar=Decimal("1"),
            amount_zar=data.amount,
            fx_gain_loss_zar=Decimal(0),
            paid_on=data.paid_on,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(payment)
            await self.posting.post(
                JournalDocumentType.PAYMENT,
                payment.id,
                f"Payment {payment_number} received",
                [
                    (CODE_BANK, data.amount, Decimal(0)),
                    (CODE_AR, Decimal(0), data.amount),
                ],
                entry_date=payment.paid_on,
            )
            invoice.amount_paid += data.amount
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

    async def _create_payment_out(
        self,
        data: PaymentCreate,
        payment_number: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> PaymentResponse:
        if data.bill_id is None:
            raise ValidationError("bill_id is required for payment out")
        if data.invoice_id is not None:
            raise ValidationError("invoice_id must not be set for payment out")

        bill = await self.bill_crud.get_by_id(data.bill_id)
        if bill is None:
            raise NotFoundError("Bill not found")

        currency = SupplierService.normalize_currency(data.currency)
        if currency != bill.currency:
            raise ValidationError("Payment currency must match bill currency")

        remaining_foreign = bill.amount_foreign
        if bill.amount_paid_zar > 0:
            raise ValidationError("Bill is already fully paid")
        if data.amount != remaining_foreign:
            raise ValidationError("Payment amount must equal the full bill amount")

        fx_to_zar = self._resolve_fx(currency, data.fx_to_zar)
        settlement_zar = convert_bill_to_zar(data.amount, currency, fx_to_zar)
        booked_zar = bill.amount_zar - bill.amount_paid_zar
        diff = settlement_zar - booked_zar
        fx_gain_loss = booked_zar - settlement_zar

        journal_lines: list[tuple[str, Decimal, Decimal]] = [
            (CODE_AP, booked_zar, Decimal(0)),
            (CODE_BANK, Decimal(0), settlement_zar),
        ]
        if diff > 0:
            journal_lines.append((CODE_FX, diff, Decimal(0)))
        elif diff < 0:
            journal_lines.append((CODE_FX, Decimal(0), abs(diff)))

        payment = Payment(
            payment_number=payment_number,
            direction=PaymentDirection.OUT,
            bill_id=bill.id,
            amount=data.amount,
            currency=currency,
            fx_to_zar=fx_to_zar,
            amount_zar=settlement_zar,
            fx_gain_loss_zar=fx_gain_loss,
            paid_on=data.paid_on,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(payment)
            await self.posting.post(
                JournalDocumentType.PAYMENT,
                payment.id,
                f"Payment {payment_number} sent",
                journal_lines,
                entry_date=payment.paid_on,
            )
            bill.amount_paid_zar = bill.amount_zar
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
        )
        return Response(content=pdf_bytes, media_type="application/pdf")

    @staticmethod
    def _resolve_fx(currency: str, fx_to_zar: Optional[Decimal]) -> Decimal:
        if currency == "ZAR":
            return Decimal("1")
        if fx_to_zar is None or fx_to_zar <= 0:
            raise ValidationError("fx_to_zar is required and must be positive for foreign currency")
        return fx_to_zar

    @staticmethod
    def _to_response(payment: Payment) -> PaymentResponse:
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
            is_reconciled=payment.is_reconciled,
            reconciled_at=payment.reconciled_at,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )
