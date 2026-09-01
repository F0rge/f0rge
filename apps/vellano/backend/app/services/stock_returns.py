from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.credit_note import CreditNoteCRUD
from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.stock_return import StockReturnCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.journal import JournalDocumentType
from app.models.stock_return import (
    StockReturn,
    StockReturnDisposition,
    StockReturnLine,
    StockReturnStatus,
)
from app.models.tax_invoice import InvoiceLine
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.stock_return import (
    StockReturnCreate,
    StockReturnLineResponse,
    StockReturnResponse,
)
from app.services.chart_of_accounts import CODE_COGS, CODE_INVENTORY, LedgerPostingService
from app.services.credit_notes import CreditNoteService
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class StockReturnsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = StockReturnCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.credit_note_crud = CreditNoteCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.stock_movements = StockMovementService(db)
        self.stocktakes = StocktakeService(db)
        self.posting = LedgerPostingService(db)
        self.credit_notes = CreditNoteService(db)

    async def list(self) -> list[StockReturnResponse]:
        rows = await self.crud.list_all()
        return [self._to_response(row) for row in rows]

    async def get(self, return_id: uuid.UUID) -> StockReturnResponse:
        return self._to_response(await self._get_or_404(return_id))

    async def create(self, data: StockReturnCreate, user_id: uuid.UUID) -> StockReturnResponse:
        invoice = await self.invoice_crud.get_by_id(data.invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")

        await self._assert_invoice_not_credited(data.invoice_id)
        await self._assert_no_active_return(data.invoice_id)

        location = await self.location_crud.get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot return to archived location")

        invoice_lines_by_id = {line.id: line for line in invoice.lines}
        line_models = self._build_line_models(
            data.lines,
            invoice_lines_by_id,
            data.disposition,
        )

        return_number = await self.crud.get_next_return_number()
        stock_return = StockReturn(
            return_number=return_number,
            invoice_id=invoice.id,
            location_id=data.location_id,
            reason=data.reason,
            disposition=data.disposition,
            notes=data.notes,
            status=StockReturnStatus.DRAFT,
            created_by_user_id=user_id,
            lines=line_models,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(stock_return)

        return self._to_response(await self._get_or_404(stock_return.id))

    async def complete(self, return_id: uuid.UUID, user_id: uuid.UUID) -> StockReturnResponse:
        stock_return = await self._require_draft(return_id)
        if not stock_return.lines:
            raise ValidationError("Return has no lines")

        await self._assert_invoice_not_credited(stock_return.invoice_id)

        invoice = await self.invoice_crud.get_by_id(stock_return.invoice_id)
        assert invoice is not None
        invoice_lines_by_id = {line.id: line for line in invoice.lines}

        if stock_return.disposition == StockReturnDisposition.RESTOCK:
            await self.stocktakes.assert_location_unlocked(stock_return.location_id)
            self._assert_restock_skus(stock_return.lines, invoice_lines_by_id)

        subtotal, vat_amount, total_inc = self._compute_credit_amounts(
            stock_return.lines,
            invoice_lines_by_id,
        )

        async with unit_of_work(self.db):
            credit_note = await self.credit_notes.create_for_return(
                invoice=invoice,
                reason=stock_return.reason.value,
                subtotal_ex_vat=subtotal,
                vat_amount=vat_amount,
                total_inc_vat=total_inc,
            )
            stock_return.credit_note_id = credit_note.id
            stock_return.status = StockReturnStatus.COMPLETED

            if stock_return.disposition == StockReturnDisposition.RESTOCK:
                total_cogs = Decimal(0)
                for line in stock_return.lines:
                    invoice_line = invoice_lines_by_id[line.invoice_line_id]
                    sku_id = invoice_line.sku_id
                    assert sku_id is not None
                    loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                        sku_id,
                        stock_return.location_id,
                    )
                    if loc_stock is None or loc_stock.unit_cost_zar is None:
                        raise ValidationError("unit cost required")
                    unit_cost = loc_stock.unit_cost_zar
                    await self.stock_movements.apply_incoming_qty(
                        sku_id=sku_id,
                        location_id=stock_return.location_id,
                        qty=line.qty,
                        unit_cost_zar=unit_cost,
                        user_id=user_id,
                        source=UnitCostAuditSource.RETURN,
                        note=f"Return {stock_return.return_number} restock",
                    )
                    total_cogs += (unit_cost * line.qty).quantize(CENT, rounding=ROUND_HALF_UP)

                if total_cogs > 0:
                    await self.posting.post(
                        JournalDocumentType.CREDIT_NOTE,
                        credit_note.id,
                        f"COGS reverse for return {stock_return.return_number}",
                        [
                            (CODE_INVENTORY, total_cogs, Decimal(0)),
                            (CODE_COGS, Decimal(0), total_cogs),
                        ],
                        entry_date=credit_note.issue_date,
                    )

        return self._to_response(await self._get_or_404(stock_return.id))

    async def cancel(self, return_id: uuid.UUID) -> StockReturnResponse:
        stock_return = await self._require_draft(return_id)
        async with unit_of_work(self.db):
            stock_return.status = StockReturnStatus.CANCELLED
        return self._to_response(await self._get_or_404(stock_return.id))

    async def _get_or_404(self, return_id: uuid.UUID) -> StockReturn:
        stock_return = await self.crud.get_by_id(return_id)
        if stock_return is None:
            raise NotFoundError("Return not found")
        return stock_return

    async def _require_draft(self, return_id: uuid.UUID) -> StockReturn:
        stock_return = await self._get_or_404(return_id)
        if stock_return.status != StockReturnStatus.DRAFT:
            raise ConflictError("Return is not a draft")
        return stock_return

    async def _assert_invoice_not_credited(self, invoice_id: uuid.UUID) -> None:
        existing_cn = await self.credit_note_crud.get_by_invoice_id(invoice_id)
        if existing_cn is not None:
            raise ConflictError("This invoice has already been credited")

    async def _assert_no_active_return(self, invoice_id: uuid.UUID) -> None:
        existing = await self.crud.get_active_by_invoice_id(invoice_id)
        if existing is not None:
            raise ConflictError("This invoice already has a return")

    def _build_line_models(
        self,
        lines: list,
        invoice_lines_by_id: dict[uuid.UUID, InvoiceLine],
        disposition: StockReturnDisposition,
    ) -> list[StockReturnLine]:
        seen_invoice_lines: set[uuid.UUID] = set()
        models: list[StockReturnLine] = []

        for line in lines:
            if line.invoice_line_id in seen_invoice_lines:
                raise ValidationError("Duplicate invoice line on return")
            seen_invoice_lines.add(line.invoice_line_id)

            invoice_line = invoice_lines_by_id.get(line.invoice_line_id)
            if invoice_line is None:
                raise ValidationError("Invoice line does not belong to this invoice")
            if line.qty > invoice_line.qty:
                raise ValidationError("Return quantity exceeds invoice line quantity")

            sku_id = invoice_line.sku_id if invoice_line.sku_id is not None else line.sku_id
            if disposition == StockReturnDisposition.RESTOCK and invoice_line.sku_id is None:
                raise ValidationError("Restock is only available for till sales")

            models.append(
                StockReturnLine(
                    invoice_line_id=line.invoice_line_id,
                    sku_id=sku_id,
                    qty=line.qty,
                )
            )

        return models

    @staticmethod
    def _assert_restock_skus(
        lines: list[StockReturnLine],
        invoice_lines_by_id: dict[uuid.UUID, InvoiceLine],
    ) -> None:
        for line in lines:
            invoice_line = invoice_lines_by_id[line.invoice_line_id]
            if invoice_line.sku_id is None:
                raise ValidationError("Restock is only available for till sales")

    @staticmethod
    def _compute_credit_amounts(
        lines: list[StockReturnLine],
        invoice_lines_by_id: dict[uuid.UUID, InvoiceLine],
    ) -> tuple[Decimal, Decimal, Decimal]:
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        for line in lines:
            invoice_line = invoice_lines_by_id[line.invoice_line_id]
            ex_vat = (Decimal(line.qty) * invoice_line.unit_ex_vat).quantize(
                CENT,
                rounding=ROUND_HALF_UP,
            )
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
        return subtotal, vat_total, total_inc

    def _to_response(self, stock_return: StockReturn) -> StockReturnResponse:
        return StockReturnResponse(
            id=stock_return.id,
            return_number=stock_return.return_number,
            invoice_id=stock_return.invoice_id,
            invoice_number=stock_return.invoice.invoice_number,
            location_id=stock_return.location_id,
            location_name=stock_return.location.name,
            credit_note_id=stock_return.credit_note_id,
            reason=stock_return.reason,
            disposition=stock_return.disposition,
            status=stock_return.status,
            notes=stock_return.notes,
            lines=[
                StockReturnLineResponse(
                    id=line.id,
                    invoice_line_id=line.invoice_line_id,
                    sku_id=line.sku_id,
                    description=line.invoice_line.description,
                    qty=line.qty,
                    unit_ex_vat=line.invoice_line.unit_ex_vat,
                )
                for line in stock_return.lines
            ],
            created_at=stock_return.created_at,
            updated_at=stock_return.updated_at,
        )
