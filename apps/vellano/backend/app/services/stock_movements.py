from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.purchase_order import LocationStockCRUD
from app.models.inventory import LocationStock
from app.models.unit_cost_audit import UnitCostAuditSource
from app.services.cost_audit import CostAuditService
from f0rge_core.exceptions import ConflictError, ValidationError


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

    async def apply_outgoing_qty(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
        qty: int,
        user_id: uuid.UUID,
        source: UnitCostAuditSource,
        note: str,
    ) -> LocationStock:
        loc_stock = await self.location_stock_crud.get_by_sku_and_location(sku_id, location_id)
        if loc_stock is None or loc_stock.on_hand < qty:
            raise ConflictError("Insufficient on-hand quantity")
        old_cost = loc_stock.unit_cost_zar
        loc_stock.on_hand -= qty
        if old_cost is not None:
            await self.cost_audit.record(
                sku_id=sku_id,
                location_id=location_id,
                old_cost_zar=old_cost,
                new_cost_zar=old_cost,
                changed_by_user_id=user_id,
                source=source,
                note=note,
            )
        return loc_stock

    async def apply_qty_delta(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
        delta: int,
        user_id: uuid.UUID,
        source: UnitCostAuditSource,
        note: str,
    ) -> Optional[LocationStock]:
        if delta == 0:
            return await self.location_stock_crud.get_by_sku_and_location(sku_id, location_id)
        if delta > 0:
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                sku_id,
                location_id,
            )
            unit_cost = loc_stock.unit_cost_zar if loc_stock is not None else None
            if unit_cost is None:
                raise ValidationError("unit cost required to increase stock")
            return await self.apply_incoming_qty(
                sku_id,
                location_id,
                delta,
                unit_cost,
                user_id,
                source,
                note,
            )
        return await self.apply_outgoing_qty(
            sku_id,
            location_id,
            -delta,
            user_id,
            source,
            note,
        )

    async def set_on_hand(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
        qty: int,
        user_id: uuid.UUID,
        source: UnitCostAuditSource,
        note: str,
        unit_cost_zar: Optional[Decimal] = None,
    ) -> Optional[LocationStock]:
        loc_stock = await self.location_stock_crud.get_by_sku_and_location(sku_id, location_id)
        current = loc_stock.on_hand if loc_stock is not None else 0
        delta = qty - current
        if delta == 0:
            return loc_stock
        if delta > 0:
            cost = unit_cost_zar
            if cost is None and loc_stock is not None:
                cost = loc_stock.unit_cost_zar
            if cost is None:
                raise ValidationError("unit cost required to increase stock")
            return await self.apply_incoming_qty(
                sku_id,
                location_id,
                delta,
                cost,
                user_id,
                source,
                note,
            )
        return await self.apply_outgoing_qty(
            sku_id,
            location_id,
            -delta,
            user_id,
            source,
            note,
        )
