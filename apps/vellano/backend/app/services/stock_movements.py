from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.purchase_order import LocationStockCRUD
from app.models.inventory import LocationStock
from app.models.unit_cost_audit import UnitCostAuditSource
from app.services.cost_audit import CostAuditService


class StockMovementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.location_stock_crud = LocationStockCRUD(db)
        self.cost_audit = CostAuditService(db)

    async def apply_incoming_qty(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
        qty: int,
        unit_cost_zar: Decimal,
        user_id: uuid.UUID,
        source: UnitCostAuditSource,
        note: str,
    ) -> LocationStock:
        loc_stock = await self.location_stock_crud.get_by_sku_and_location(sku_id, location_id)
        if loc_stock is None:
            loc_stock = LocationStock(
                sku_id=sku_id,
                location_id=location_id,
                on_hand=0,
            )
            await self.location_stock_crud.add_and_flush(loc_stock)

        old_on_hand = loc_stock.on_hand
        old_cost = loc_stock.unit_cost_zar
        new_on_hand = old_on_hand + qty
        if old_on_hand == 0 or old_cost is None:
            blended = unit_cost_zar
        else:
            blended = (old_on_hand * old_cost + qty * unit_cost_zar) / new_on_hand
        loc_stock.on_hand = new_on_hand
        loc_stock.unit_cost_zar = blended
        await self.cost_audit.record(
            sku_id=sku_id,
            location_id=location_id,
            old_cost_zar=old_cost,
            new_cost_zar=blended,
            changed_by_user_id=user_id,
            source=source,
            note=note,
        )
        return loc_stock
