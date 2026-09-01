from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.purchase_order import LocationStockCRUD, SkuStockCRUD
from app.models.inventory import LocationStock
from app.models.sku import Sku
from app.schemas.inventory import InventorySkuResponse, LocationStockResponse
from app.services.packing_sheet import sku_level_unit_cost


class InventoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sku_stock_crud = SkuStockCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)

    async def list(self) -> list[InventorySkuResponse]:
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
            locations = [
                LocationStockResponse(
                    location_id=ls.location_id,
                    location_name=ls.location.name,
                    on_hand=ls.on_hand,
                    unit_cost_zar=ls.unit_cost_zar,
                )
                for ls in loc_stocks
            ]

            unit_cost = sku_level_unit_cost([(ls.on_hand, ls.unit_cost_zar) for ls in loc_stocks])

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
