from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.stocktake import StocktakeCRUD, StocktakeLineCRUD
from app.models.stocktake import Stocktake, StocktakeLine, StocktakeStatus
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.stocktake import (
    StocktakeCreate,
    StocktakeLineCountUpdate,
    StocktakeLineResponse,
    StocktakeLookupRequest,
    StocktakeResponse,
)
from app.services.stock_movements import StockMovementService
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class StocktakeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = StocktakeCRUD(db)
        self.line_crud = StocktakeLineCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.stock_movements = StockMovementService(db)

    async def assert_location_unlocked(self, location_id: uuid.UUID) -> None:
        existing = await self.crud.get_in_progress_for_location(location_id)
        if existing is not None:
            raise ConflictError("Location is locked for stocktake")

    async def list(self) -> list[StocktakeResponse]:
        return [self._to_response(row) for row in await self.crud.list_all()]

    async def get(self, stocktake_id: uuid.UUID) -> StocktakeResponse:
        return self._to_response(await self._get_or_404(stocktake_id))

    async def start(self, data: StocktakeCreate, user_id: uuid.UUID) -> StocktakeResponse:
        location = await self.location_crud.get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot stocktake archived location")
        await self.assert_location_unlocked(data.location_id)

        skus = await self.sku_crud.list_all()
        stocks = await self.location_stock_crud.list_by_location_id(data.location_id)
        on_hand_by_sku = {row.sku_id: row.on_hand for row in stocks}

        stocktake = Stocktake(
            location_id=data.location_id,
            status=StocktakeStatus.IN_PROGRESS,
            started_at=datetime.datetime.utcnow(),
            created_by_user_id=user_id,
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(stocktake)
                for sku in skus:
                    await self.line_crud.add_and_flush(
                        StocktakeLine(
                            stocktake_id=stocktake.id,
                            sku_id=sku.id,
                            expected_qty=on_hand_by_sku.get(sku.id, 0),
                        )
                    )
        except IntegrityError as exc:
            raise ConflictError("Location is locked for stocktake") from exc

        reloaded = await self._get_or_404(stocktake.id)
        return self._to_response(reloaded)

    async def update_line(
        self,
        stocktake_id: uuid.UUID,
        line_id: uuid.UUID,
        data: StocktakeLineCountUpdate,
    ) -> StocktakeLineResponse:
        stocktake = await self._require_in_progress(stocktake_id)
        line = await self.line_crud.get_by_id(stocktake.id, line_id)
        if line is None:
            raise NotFoundError("Stocktake line not found")

        async with unit_of_work(self.db):
            line.counted_qty = data.counted_qty

        reloaded = await self.line_crud.get_by_id(stocktake.id, line_id)
        assert reloaded is not None
        return self._line_response(reloaded)

    async def lookup(
        self,
        stocktake_id: uuid.UUID,
        data: StocktakeLookupRequest,
    ) -> StocktakeLineResponse:
        await self._get_or_404(stocktake_id)
        line = await self.line_crud.get_by_barcode(stocktake_id, data.barcode)
        if line is None:
            raise NotFoundError("Stocktake line not found")
        return self._line_response(line)

    async def complete(self, stocktake_id: uuid.UUID, user_id: uuid.UUID) -> StocktakeResponse:
        stocktake = await self._require_in_progress(stocktake_id)
        async with unit_of_work(self.db):
            for line in stocktake.lines:
                if line.counted_qty is None:
                    continue
                delta = line.counted_qty - line.expected_qty
                await self.stock_movements.apply_qty_delta(
                    sku_id=line.sku_id,
                    location_id=stocktake.location_id,
                    delta=delta,
                    user_id=user_id,
                    source=UnitCostAuditSource.STOCKTAKE,
                    note=f"Stocktake qty {delta:+d}",
                )
            stocktake.status = StocktakeStatus.COMPLETED
            stocktake.completed_at = datetime.datetime.utcnow()

        return self._to_response(await self._get_or_404(stocktake.id))

    async def cancel(self, stocktake_id: uuid.UUID) -> StocktakeResponse:
        stocktake = await self._require_in_progress(stocktake_id)
        async with unit_of_work(self.db):
            stocktake.status = StocktakeStatus.CANCELLED
            stocktake.completed_at = datetime.datetime.utcnow()
        return self._to_response(await self._get_or_404(stocktake.id))

    async def _get_or_404(self, stocktake_id: uuid.UUID) -> Stocktake:
        stocktake = await self.crud.get_by_id(stocktake_id)
        if stocktake is None:
            raise NotFoundError("Stocktake not found")
        return stocktake

    async def _require_in_progress(self, stocktake_id: uuid.UUID) -> Stocktake:
        stocktake = await self._get_or_404(stocktake_id)
        if stocktake.status != StocktakeStatus.IN_PROGRESS:
            raise ConflictError("Stocktake is not in progress")
        return stocktake

    def _to_response(self, stocktake: Stocktake) -> StocktakeResponse:
        lines = sorted(stocktake.lines, key=lambda line: line.sku.our_ref)
        return StocktakeResponse(
            id=stocktake.id,
            location_id=stocktake.location_id,
            location_name=stocktake.location.name,
            status=stocktake.status,
            started_at=stocktake.started_at,
            completed_at=stocktake.completed_at,
            lines=[self._line_response(line) for line in lines],
        )

    @staticmethod
    def _line_response(line: StocktakeLine) -> StocktakeLineResponse:
        variance: Optional[int]
        if line.counted_qty is None:
            variance = None
        else:
            variance = line.counted_qty - line.expected_qty
        return StocktakeLineResponse(
            id=line.id,
            sku_id=line.sku_id,
            our_ref=line.sku.our_ref,
            our_barcode=line.sku.our_barcode,
            name=line.sku.name,
            expected_qty=line.expected_qty,
            counted_qty=line.counted_qty,
            variance=variance,
        )
