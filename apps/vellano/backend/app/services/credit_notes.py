from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.credit_note import CreditNoteCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.credit_note import CreditNote
from app.models.journal import JournalDocumentType
from app.models.tax_invoice import TaxInvoice
from app.schemas.credit_note import CreditNoteCreate, CreditNoteResponse
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_SALES,
    CODE_VAT,
    LedgerPostingService,
)
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class CreditNoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CreditNoteCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.posting = LedgerPostingService(db)

    async def list(self) -> list[CreditNoteResponse]:
        credit_notes = await self.crud.list_all()
        return [self._to_response(cn) for cn in credit_notes]

    async def get(self, credit_note_id: uuid.UUID) -> CreditNoteResponse:
        credit_note = await self.crud.get_by_id(credit_note_id)
        if credit_note is None:
            raise NotFoundError("Credit note not found")
        return self._to_response(credit_note)

    async def create(self, data: CreditNoteCreate) -> CreditNoteResponse:
        invoice = await self.invoice_crud.get_by_id(data.invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")

        existing = await self.crud.get_by_invoice_id(data.invoice_id)
        if existing is not None:
            raise ConflictError("This invoice has already been credited")

        async with unit_of_work(self.db):
            credit_note = await self._create_and_post(
                invoice=invoice,
                reason=data.reason,
                subtotal_ex_vat=invoice.subtotal_ex_vat,
                vat_amount=invoice.vat_amount,
                total_inc_vat=invoice.total_inc_vat,
            )
            await self.crud.commit_refresh(credit_note)

        reloaded = await self.crud.get_by_id(credit_note.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def create_for_return(
        self,
        invoice: TaxInvoice,
        reason: Optional[str],
        subtotal_ex_vat: Decimal,
        vat_amount: Decimal,
        total_inc_vat: Decimal,
    ) -> CreditNote:
        """Create and post a credit note inside the caller's unit_of_work."""
        return await self._create_and_post(
            invoice=invoice,
            reason=reason,
            subtotal_ex_vat=subtotal_ex_vat,
            vat_amount=vat_amount,
            total_inc_vat=total_inc_vat,
        )

    async def _create_and_post(
        self,
        invoice: TaxInvoice,
        reason: Optional[str],
        subtotal_ex_vat: Decimal,
        vat_amount: Decimal,
        total_inc_vat: Decimal,
    ) -> CreditNote:
        credit_note_number = await self.crud.get_next_credit_note_number()
        credit_note = CreditNote(
            credit_note_number=credit_note_number,
            invoice_id=invoice.id,
            reason=reason,
            issue_date=datetime.date.today(),
            subtotal_ex_vat=subtotal_ex_vat,
            vat_amount=vat_amount,
            total_inc_vat=total_inc_vat,
        )
        await self.crud.add_and_flush(credit_note)
        await self.posting.post(
            JournalDocumentType.CREDIT_NOTE,
            credit_note.id,
            f"Credit note {credit_note_number}",
            [
                (CODE_SALES, subtotal_ex_vat, Decimal(0)),
                (CODE_VAT, vat_amount, Decimal(0)),
                (CODE_AR, Decimal(0), total_inc_vat),
            ],
            entry_date=credit_note.issue_date,
        )
        return credit_note

    @staticmethod
    def _to_response(credit_note: CreditNote) -> CreditNoteResponse:
        return CreditNoteResponse(
            id=credit_note.id,
            credit_note_number=credit_note.credit_note_number,
            invoice_id=credit_note.invoice_id,
            invoice_number=credit_note.invoice.invoice_number,
            reason=credit_note.reason,
            issue_date=credit_note.issue_date,
            subtotal_ex_vat=credit_note.subtotal_ex_vat,
            vat_amount=credit_note.vat_amount,
            total_inc_vat=credit_note.total_inc_vat,
            created_at=credit_note.created_at,
            updated_at=credit_note.updated_at,
        )
