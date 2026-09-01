from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.transfer import TransferCreate, TransferLocationStock, TransferResponse
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class TransferService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.location_crud = LocationCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.stock_movements = StockMovementService(db)

    async def transfer(self, data: TransferCreate, user_id: uuid.UUID) -> TransferResponse:
        stocktakes = StocktakeService(self.db)
        await stocktakes.assert_location_unlocked(data.from_location_id)
        await stocktakes.assert_location_unlocked(data.to_location_id)
        if data.from_location_id == data.to_location_id:
            raise ValidationError("Source and destination locations must differ")

        sku = await self.sku_crud.get_by_id(data.sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")

        from_location = await self.location_crud.get_by_id(data.from_location_id)
        if from_location is None:
            raise NotFoundError("Source location not found")
        if from_location.is_archived:
            raise ConflictError("Cannot transfer from archived location")

        to_location = await self.location_crud.get_by_id(data.to_location_id)
        if to_location is None:
            raise NotFoundError("Destination location not found")
        if to_location.is_archived:
            raise ConflictError("Cannot transfer into archived location")

        source_stock = await self.location_stock_crud.get_by_sku_and_location(
            data.sku_id,
            data.from_location_id,
        )
        if source_stock is None or source_stock.on_hand < data.qty:
            raise ConflictError("Insufficient on-hand quantity at source location")

        unit_cost = source_stock.unit_cost_zar
        if unit_cost is None:
            raise ConflictError("Source location has no unit cost for this SKU")

        async with unit_of_work(self.db):
            await self.stock_movements.apply_outgoing_qty(
                sku_id=data.sku_id,
                location_id=data.from_location_id,
                qty=data.qty,
                user_id=user_id,
                source=UnitCostAuditSource.RECEIVE,
                note="Transfer out",
                bin_id=data.from_bin_id,
                record_audit=False,
            )
            dest_stock = await self.stock_movements.apply_incoming_qty(
                sku_id=data.sku_id,
                location_id=data.to_location_id,
                qty=data.qty,
                unit_cost_zar=unit_cost,
                user_id=user_id,
                source=UnitCostAuditSource.RECEIVE,
                note="Transfer in",
                bin_id=data.to_bin_id,
                record_audit=False,
            )

        source_stock = await self.location_stock_crud.get_by_sku_and_location(
            data.sku_id,
            data.from_location_id,
        )
        assert source_stock is not None

        return TransferResponse(
            sku_id=sku.id,
            our_ref=sku.our_ref,
            name=sku.name,
            qty=data.qty,
            from_location=TransferLocationStock(
                location_id=from_location.id,
                location_name=from_location.name,
                on_hand=source_stock.on_hand,
                unit_cost_zar=source_stock.unit_cost_zar,
            ),
            to_location=TransferLocationStock(
                location_id=to_location.id,
                location_name=to_location.name,
                on_hand=dest_stock.on_hand,
                unit_cost_zar=dest_stock.unit_cost_zar,
            ),
        )
