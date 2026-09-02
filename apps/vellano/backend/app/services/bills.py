from __future__ import annotations

import asyncio
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.bill import BillCRUD
from app.crud.supplier import SupplierCRUD
from app.models.bill import Bill, BillLine
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.journal import JournalDocumentType
from app.services.books_events import BooksEventService
from app.schemas.bill import BillCreate, BillLineResponse, BillResponse
from app.services.chart_of_accounts import CODE_AP, CODE_INVENTORY, LedgerPostingService
from app.services.object_storage import save_bytes
from app.services.packing_sheet import convert_bill_to_zar
from app.services.stored_pdf import serve_stored_pdf
from app.services.suppliers import SupplierService
from app.services.vat import CENT
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class BillService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = BillCRUD(db)
        self.supplier_crud = SupplierCRUD(db)
        self.posting = LedgerPostingService(db)
        self.events = BooksEventService(db)

    async def list(self) -> list[BillResponse]:
        bills = await self.crud.list_all()
        return [self._to_response(bill) for bill in bills]

    async def get(self, bill_id: uuid.UUID) -> BillResponse:
        bill = await self.crud.get_by_id(bill_id)
        if bill is None:
            raise NotFoundError("Bill not found")
        return self._to_response(bill)

    async def create(self, data: BillCreate, user_id: Optional[uuid.UUID] = None) -> BillResponse:
        supplier = await self.supplier_crud.get_by_id(data.supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier not found")

        currency = SupplierService.normalize_currency(data.currency)
        fx_to_zar = self._resolve_fx(currency, data.fx_to_zar)

        amount_foreign = Decimal(0)
        line_models: list[BillLine] = []
        for index, line in enumerate(data.lines):
            line_amount = (Decimal(line.qty) * line.unit_amount).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            amount_foreign += line_amount
            line_models.append(
                BillLine(
                    description=line.description,
                    qty=line.qty,
                    unit_amount=line.unit_amount,
                    amount_foreign=line_amount,
                    sort_order=index,
                )
            )

        if amount_foreign <= 0:
            raise ValidationError("Bill total must be positive")

        amount_zar = convert_bill_to_zar(amount_foreign, currency, fx_to_zar)
        bill_number = await self.crud.get_next_bill_number()
        bill = Bill(
            bill_number=bill_number,
            supplier_id=data.supplier_id,
            supplier_ref=data.supplier_ref,
            issue_date=data.issue_date,
            currency=currency,
            fx_to_zar=fx_to_zar,
            amount_foreign=amount_foreign,
            amount_zar=amount_zar,
            amount_paid_zar=Decimal(0),
            lines=line_models,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(bill)
            await self.posting.post(
                JournalDocumentType.BILL,
                bill.id,
                f"Supplier bill {bill_number}",
                [
                    (CODE_INVENTORY, amount_zar, Decimal(0)),
                    (CODE_AP, Decimal(0), amount_zar),
                ],
                entry_date=bill.issue_date,
            )
            await self.events.record(
                BooksDocumentType.BILL,
                bill.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
            )
            await self.crud.commit_refresh(bill)

        reloaded = await self.crud.get_by_id(bill.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def upload_attachment(self, bill_id: uuid.UUID, file: UploadFile) -> BillResponse:
        bill = await self.crud.get_by_id(bill_id)
        if bill is None:
            raise NotFoundError("Bill not found")

        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise ValidationError("PDF file is required")

        relative_path = f"bills/{bill_id}.pdf"
        try:
            storage_key = await asyncio.to_thread(save_bytes, relative_path, pdf_bytes)
        except FileExistsError as exc:
            raise ConflictError("Bill attachment already exists") from exc

        bill.pdf_storage_key = storage_key
        await self.crud.commit_refresh(bill)
        reloaded = await self.crud.get_by_id(bill.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def serve_attachment(self, bill_id: uuid.UUID) -> Response:
        bill = await self.crud.get_by_id(bill_id)
        if bill is None:
            raise NotFoundError("Bill not found")
        return await serve_stored_pdf(
            bill.pdf_storage_key,
            f"{bill.bill_number}.pdf",
            "Bill attachment not found",
        )

    @staticmethod
    def _resolve_fx(currency: str, fx_to_zar: Optional[Decimal]) -> Decimal:
        if currency == "ZAR":
            return Decimal("1")
        if fx_to_zar is None or fx_to_zar <= 0:
            raise ValidationError("fx_to_zar is required and must be positive for foreign currency")
        return fx_to_zar

    @staticmethod
    def _to_response(bill: Bill) -> BillResponse:
        balance_zar = bill.amount_zar - bill.amount_paid_zar
        return BillResponse(
            id=bill.id,
            bill_number=bill.bill_number,
            supplier_id=bill.supplier_id,
            supplier_name=bill.supplier.name,
            supplier_ref=bill.supplier_ref,
            issue_date=bill.issue_date,
            currency=bill.currency,
            fx_to_zar=bill.fx_to_zar,
            amount_foreign=bill.amount_foreign,
            amount_zar=bill.amount_zar,
            amount_paid_zar=bill.amount_paid_zar,
            balance_zar=balance_zar,
            pdf_storage_key=bill.pdf_storage_key,
            lines=[
                BillLineResponse(
                    id=line.id,
                    description=line.description,
                    qty=line.qty,
                    unit_amount=line.unit_amount,
                    amount_foreign=line.amount_foreign,
                    sort_order=line.sort_order,
                )
                for line in bill.lines
            ],
            created_at=bill.created_at,
            updated_at=bill.updated_at,
        )
