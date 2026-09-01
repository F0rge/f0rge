from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.location_bin import BinStockCRUD
from app.crud.purchase_order import LocationStockCRUD, SkuStockCRUD
from app.models.inventory import LocationStock
from app.models.sku import Sku
from app.permissions import STOCK_COST_VIEW
from app.schemas.inventory import InventorySkuResponse, LocationStockResponse
from app.schemas.location_bin import BinOnHandResponse
from app.services.packing_sheet import sku_level_unit_cost
from app.services.permissions import PermissionService


class InventoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sku_stock_crud = SkuStockCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.bin_stock_crud = BinStockCRUD(db)

    async def list(self, user_id: Optional[uuid.UUID] = None) -> list[InventorySkuResponse]:
        hide_cost = True
        if user_id is not None:
            hide_cost = not await PermissionService(self.db).has_permission(
                user_id, STOCK_COST_VIEW
            )
        sku_ids_with_movement: set = set()

        on_order_rows = await self.sku_stock_crud.list_with_movement()
        for row in on_order_rows:
            sku_ids_with_movement.add(row.sku_id)

        on_hand_rows = await self.location_stock_crud.list_with_on_hand()
        for row in on_hand_rows:
            sku_ids_with_movement.add(row.sku_id)

        if not sku_ids_with_movement:
            return []

        result = await self.db.execute(
            select(Sku).where(Sku.id.in_(sku_ids_with_movement)).order_by(Sku.our_ref)
        )
        skus = list(result.scalars().all())

        responses: list[InventorySkuResponse] = []
        for sku in skus:
            stock = await self.sku_stock_crud.get_by_sku_id(sku.id)
            on_order = stock.on_order if stock is not None else 0

            loc_stocks = await self._get_location_stocks_for_sku(sku.id)
            on_hand = sum(ls.on_hand for ls in loc_stocks)
            bin_rows = await self.bin_stock_crud.list_nonzero_for_skus([sku.id])
            locations = [
                LocationStockResponse(
                    location_id=ls.location_id,
                    location_name=ls.location.name,
                    on_hand=ls.on_hand,
                    unit_cost_zar=None if hide_cost else ls.unit_cost_zar,
                    bins=[
                        BinOnHandResponse(
                            bin_id=row.bin_id,
                            code=row.bin.code,
                            on_hand=row.on_hand,
                        )
                        for row in bin_rows
                        if row.bin.location_id == ls.location_id
                    ],
                )
                for ls in loc_stocks
            ]

            unit_cost = sku_level_unit_cost([(ls.on_hand, ls.unit_cost_zar) for ls in loc_stocks])
            if hide_cost:
                unit_cost = None

            responses.append(
                InventorySkuResponse(
                    sku_id=sku.id,
                    our_ref=sku.our_ref,
                    name=sku.name,
                    on_order=on_order,
                    on_hand=on_hand,
                    sellable=on_hand > 0,
                    unit_cost_zar=unit_cost,
                    locations=locations,
                )
            )

        return responses

    async def _get_location_stocks_for_sku(self, sku_id) -> list[LocationStock]:
        result = await self.db.execute(
            select(LocationStock)
            .options(selectinload(LocationStock.location))
            .where(LocationStock.sku_id == sku_id, LocationStock.on_hand > 0)
        )
        return list(result.scalars().all())
