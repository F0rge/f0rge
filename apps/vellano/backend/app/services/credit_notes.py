from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.credit_note import CreditNoteCRUD
from app.crud.sku import SkuCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.credit_note import CreditNote
from app.models.journal import JournalDocumentType
from app.models.sku import Sku
from app.models.tax_invoice import TaxInvoice
from app.schemas.credit_note import CreditNoteCreate, CreditNoteResponse
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_VAT,
    LedgerPostingService,
)
from app.services.invoice_pdf import build_tax_invoice_pdf
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class CreditNoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CreditNoteCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)

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
                sales_splits=[(line.sku_id, line.ex_vat) for line in invoice.lines],
            )
            await self.crud.commit_refresh(credit_note)

        reloaded = await self.crud.get_by_id(credit_note.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def serve_pdf(self, credit_note_id: uuid.UUID) -> Response:
        credit_note = await self.crud.get_by_id(credit_note_id)
        if credit_note is None:
            raise NotFoundError("Credit note not found")
        invoice = credit_note.invoice
        customer = invoice.customer
        lines = [
            (
                line.description,
                line.qty,
                f"{line.unit_ex_vat:.2f}",
                f"{line.ex_vat:.2f}",
                f"{line.vat_amount:.2f}",
                f"{line.inc_vat:.2f}",
            )
            for line in invoice.lines
        ]
        pdf_bytes = build_tax_invoice_pdf(
            invoice_number=credit_note.credit_note_number,
            issue_date=credit_note.issue_date.isoformat(),
            customer_name=customer.name if customer else "",
            customer_vat=customer.vat_number if customer else None,
            customer_address=customer.billing_address if customer else None,
            lines=lines,
            subtotal_ex_vat=f"{credit_note.subtotal_ex_vat:.2f}",
            vat_amount=f"{credit_note.vat_amount:.2f}",
            total_inc_vat=f"{credit_note.total_inc_vat:.2f}",
            title="Credit Note",
            original_invoice_number=invoice.invoice_number,
            credit_reason=credit_note.reason,
        )
        return Response(content=pdf_bytes, media_type="application/pdf")

    async def create_for_return(
        self,
        invoice: TaxInvoice,
        reason: Optional[str],
        subtotal_ex_vat: Decimal,
        vat_amount: Decimal,
        total_inc_vat: Decimal,
        sales_splits: list[tuple[Optional[uuid.UUID], Decimal]],
    ) -> CreditNote:
        """Create and post a credit note inside the caller's unit_of_work."""
        return await self._create_and_post(
            invoice=invoice,
            reason=reason,
            subtotal_ex_vat=subtotal_ex_vat,
            vat_amount=vat_amount,
            total_inc_vat=total_inc_vat,
            sales_splits=sales_splits,
        )

    async def _create_and_post(
        self,
        invoice: TaxInvoice,
        reason: Optional[str],
        subtotal_ex_vat: Decimal,
        vat_amount: Decimal,
        total_inc_vat: Decimal,
        sales_splits: list[tuple[Optional[uuid.UUID], Decimal]],
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
        sales_parts: list[tuple[str, Decimal, Decimal]] = []
        for sku_id, amount in sales_splits:
            sku = await self._sku_for_id(sku_id)
            sales_code = await self.category_posting.sales_code_for_sku(sku)
            sales_parts.append((sales_code, amount, Decimal(0)))
        await self.posting.post(
            JournalDocumentType.CREDIT_NOTE,
            credit_note.id,
            f"Credit note {credit_note_number}",
            self.category_posting.collapse(
                [
                    *sales_parts,
                    (CODE_VAT, vat_amount, Decimal(0)),
                    (CODE_AR, Decimal(0), total_inc_vat),
                ]
            ),
            entry_date=credit_note.issue_date,
        )
        return credit_note

    async def _sku_for_id(self, sku_id: Optional[uuid.UUID]) -> Optional[Sku]:
        if sku_id is None:
            return None
        return await self.sku_crud.get_by_id(sku_id)

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
