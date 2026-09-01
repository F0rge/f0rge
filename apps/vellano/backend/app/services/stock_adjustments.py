from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.stock_adjustment import StockAdjustmentCRUD, StockAdjustmentLineCRUD
from app.models.journal import JournalDocumentType
from app.models.stock_adjustment import (
    StockAdjustment,
    StockAdjustmentLine,
    StockAdjustmentReason,
    StockAdjustmentStatus,
)
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.stock_adjustment import (
    StockAdjustmentCreate,
    StockAdjustmentLineCreate,
    StockAdjustmentLineResponse,
    StockAdjustmentLineUpdate,
    StockAdjustmentResponse,
)
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import (
    CODE_INVENTORY,
    CODE_OPENING,
    LedgerPostingService,
)
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

_CENT = Decimal("0.01")
_NEGATIVE_REASONS = frozenset(
    {
        StockAdjustmentReason.DAMAGE,
        StockAdjustmentReason.THEFT,
        StockAdjustmentReason.WRITE_OFF,
    }
)


class StockAdjustmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = StockAdjustmentCRUD(db)
        self.line_crud = StockAdjustmentLineCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.stock_movements = StockMovementService(db)
        self.stocktakes = StocktakeService(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)

    async def list(self) -> list[StockAdjustmentResponse]:
        rows = await self.crud.list_all()
        return [await self._to_response(row) for row in rows]

    async def get(self, adjustment_id: uuid.UUID) -> StockAdjustmentResponse:
        return await self._to_response(await self._get_or_404(adjustment_id))

    async def create(
        self, data: StockAdjustmentCreate, user_id: uuid.UUID
    ) -> StockAdjustmentResponse:
        location = await self.location_crud.get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot adjust archived location")
        await self.stocktakes.assert_location_unlocked(data.location_id)

        adjustment = StockAdjustment(
            location_id=data.location_id,
            reason=data.reason,
            notes=data.notes,
            status=StockAdjustmentStatus.DRAFT,
            created_by_user_id=user_id,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(adjustment)

        return await self._to_response(await self._get_or_404(adjustment.id))

    async def add_line(
        self,
        adjustment_id: uuid.UUID,
        data: StockAdjustmentLineCreate,
    ) -> StockAdjustmentLineResponse:
        adjustment = await self._require_draft(adjustment_id)
        self._validate_qty_delta(adjustment.reason, data.qty_delta)
        sku = await self.sku_crud.get_by_id(data.sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")

        line = StockAdjustmentLine(
            adjustment_id=adjustment.id,
            sku_id=data.sku_id,
            qty_delta=data.qty_delta,
            unit_cost_zar=data.unit_cost_zar,
        )
        async with unit_of_work(self.db):
            await self.line_crud.add_and_flush(line)

        reloaded = await self.line_crud.get_by_id(adjustment.id, line.id)
        assert reloaded is not None
        return await self._line_response(
            reloaded,
            adjustment.location_id,
            status=adjustment.status,
        )

    async def update_line(
        self,
        adjustment_id: uuid.UUID,
        line_id: uuid.UUID,
        data: StockAdjustmentLineUpdate,
    ) -> StockAdjustmentLineResponse:
        adjustment = await self._require_draft(adjustment_id)
        line = await self.line_crud.get_by_id(adjustment.id, line_id)
        if line is None:
            raise NotFoundError("Adjustment line not found")

        updates = data.model_dump(exclude_unset=True)
        if "qty_delta" in updates:
            if updates["qty_delta"] is None:
                raise ValidationError("qty_delta must not be zero")
            self._validate_qty_delta(adjustment.reason, updates["qty_delta"])
            line.qty_delta = updates["qty_delta"]
        if "unit_cost_zar" in updates:
            line.unit_cost_zar = updates["unit_cost_zar"]

        async with unit_of_work(self.db):
            await self.line_crud.flush()

        reloaded = await self.line_crud.get_by_id(adjustment.id, line_id)
        assert reloaded is not None
        return await self._line_response(
            reloaded,
            adjustment.location_id,
            status=adjustment.status,
        )

    async def delete_line(self, adjustment_id: uuid.UUID, line_id: uuid.UUID) -> None:
        adjustment = await self._require_draft(adjustment_id)
        line = await self.line_crud.get_by_id(adjustment.id, line_id)
        if line is None:
            raise NotFoundError("Adjustment line not found")
        async with unit_of_work(self.db):
            await self.line_crud.delete(line)

    async def complete(
        self, adjustment_id: uuid.UUID, user_id: uuid.UUID
    ) -> StockAdjustmentResponse:
        adjustment = await self._require_draft(adjustment_id)
        if not adjustment.lines:
            raise ValidationError("Adjustment has no lines")
        await self.stocktakes.assert_location_unlocked(adjustment.location_id)

        prepared: list[tuple[StockAdjustmentLine, Decimal, bool]] = []
        for line in adjustment.lines:
            self._validate_qty_delta(adjustment.reason, line.qty_delta)
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                line.sku_id,
                adjustment.location_id,
            )
            existing_cost = loc_stock.unit_cost_zar if loc_stock is not None else None
            if line.qty_delta > 0:
                unit_cost = line.unit_cost_zar if line.unit_cost_zar is not None else existing_cost
            else:
                unit_cost = existing_cost
            if unit_cost is None:
                raise ValidationError("unit cost required")
            prepared.append((line, unit_cost, line.qty_delta > 0))

        async with unit_of_work(self.db):
            increase_total = Decimal(0)
            journal_lines: list[tuple[str, Decimal, Decimal]] = []
            for line, unit_cost, is_increase in prepared:
                amount = (Decimal(abs(line.qty_delta)) * unit_cost).quantize(
                    _CENT,
                    rounding=ROUND_HALF_UP,
                )
                note = f"Adjustment {adjustment.reason.value} qty {line.qty_delta:+d}"
                if is_increase:
                    await self.stock_movements.apply_incoming_qty(
                        sku_id=line.sku_id,
                        location_id=adjustment.location_id,
                        qty=line.qty_delta,
                        unit_cost_zar=unit_cost,
                        user_id=user_id,
                        source=UnitCostAuditSource.ADJUSTMENT,
                        note=note,
                    )
                    increase_total += amount
                else:
                    await self.stock_movements.apply_outgoing_qty(
                        sku_id=line.sku_id,
                        location_id=adjustment.location_id,
                        qty=-line.qty_delta,
                        user_id=user_id,
                        source=UnitCostAuditSource.ADJUSTMENT,
                        note=note,
                    )
                    if adjustment.reason == StockAdjustmentReason.COUNT_FIX:
                        expense_code = await self.category_posting.count_var_code_for_sku(line.sku)
                    else:
                        expense_code = await self.category_posting.stock_adj_code_for_sku(line.sku)
                    journal_lines.append((expense_code, amount, Decimal(0)))
                    journal_lines.append((CODE_INVENTORY, Decimal(0), amount))

            if increase_total > 0:
                journal_lines.append((CODE_INVENTORY, increase_total, Decimal(0)))
                journal_lines.append((CODE_OPENING, Decimal(0), increase_total))
            journal_lines = self.category_posting.collapse(journal_lines)
            if journal_lines:
                await self.posting.post(
                    JournalDocumentType.STOCK_ADJUSTMENT,
                    adjustment.id,
                    f"Stock adjustment {adjustment.reason.value}",
                    journal_lines,
                )
            adjustment.status = StockAdjustmentStatus.COMPLETED

        return await self._to_response(await self._get_or_404(adjustment.id))

    async def cancel(self, adjustment_id: uuid.UUID) -> StockAdjustmentResponse:
        adjustment = await self._require_draft(adjustment_id)
        async with unit_of_work(self.db):
            adjustment.status = StockAdjustmentStatus.CANCELLED
        return await self._to_response(await self._get_or_404(adjustment.id))

    async def _get_or_404(self, adjustment_id: uuid.UUID) -> StockAdjustment:
        adjustment = await self.crud.get_by_id(adjustment_id)
        if adjustment is None:
            raise NotFoundError("Adjustment not found")
        return adjustment

    async def _require_draft(self, adjustment_id: uuid.UUID) -> StockAdjustment:
        adjustment = await self._get_or_404(adjustment_id)
        if adjustment.status != StockAdjustmentStatus.DRAFT:
            raise ConflictError("Adjustment is not a draft")
        return adjustment

    @staticmethod
    def _validate_qty_delta(reason: StockAdjustmentReason, qty_delta: int) -> None:
        if qty_delta == 0:
            raise ValidationError("qty_delta must not be zero")
        if reason == StockAdjustmentReason.OPENING and qty_delta <= 0:
            raise ValidationError("opening adjustments must increase quantity")
        if reason in _NEGATIVE_REASONS and qty_delta >= 0:
            raise ValidationError("qty_delta must be negative for this reason")

    async def _on_hand(self, sku_id: uuid.UUID, location_id: uuid.UUID) -> int:
        loc_stock = await self.location_stock_crud.get_by_sku_and_location(sku_id, location_id)
        if loc_stock is None:
            return 0
        return loc_stock.on_hand

    async def _line_response(
        self,
        line: StockAdjustmentLine,
        location_id: uuid.UUID,
        on_hand_by_sku: Optional[dict[uuid.UUID, int]] = None,
        status: StockAdjustmentStatus = StockAdjustmentStatus.DRAFT,
    ) -> StockAdjustmentLineResponse:
        if on_hand_by_sku is None:
            live = await self._on_hand(line.sku_id, location_id)
        else:
            live = on_hand_by_sku.get(line.sku_id, 0)
        if status == StockAdjustmentStatus.COMPLETED:
            current_qty = live - line.qty_delta
            new_qty = live
        else:
            current_qty = live
            new_qty = live + line.qty_delta
        return StockAdjustmentLineResponse(
            id=line.id,
            sku_id=line.sku_id,
            our_ref=line.sku.our_ref,
            name=line.sku.name,
            qty_delta=line.qty_delta,
            unit_cost_zar=line.unit_cost_zar,
            current_qty=current_qty,
            new_qty=new_qty,
        )

    async def _to_response(self, adjustment: StockAdjustment) -> StockAdjustmentResponse:
        stocks = await self.location_stock_crud.list_by_location_id(adjustment.location_id)
        on_hand_by_sku = {row.sku_id: row.on_hand for row in stocks}
        lines = sorted(adjustment.lines, key=lambda line: line.sku.our_ref)
        return StockAdjustmentResponse(
            id=adjustment.id,
            location_id=adjustment.location_id,
            location_name=adjustment.location.name,
            reason=adjustment.reason,
            notes=adjustment.notes,
            status=adjustment.status,
            lines=[
                await self._line_response(
                    line,
                    adjustment.location_id,
                    on_hand_by_sku,
                    adjustment.status,
                )
                for line in lines
            ],
            created_at=adjustment.created_at,
            updated_at=adjustment.updated_at,
        )
