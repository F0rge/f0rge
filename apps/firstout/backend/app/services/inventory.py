from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location_bin import BinStockCRUD
from app.crud.purchase_order import LocationStockCRUD, SkuStockCRUD
from app.crud.sku import SkuCRUD
from app.models.inventory import LocationStock
from app.models.location_bin import BinStock
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
        hide_cost = await self._hide_cost(user_id)
        on_order_rows = await self.sku_stock_crud.list_with_movement()
        on_hand_rows = await self.location_stock_crud.list_with_on_hand()

        sku_by_id: dict[uuid.UUID, Sku] = {}
        on_order_by_sku: dict[uuid.UUID, int] = {}
        for row in on_order_rows:
            sku_by_id[row.sku_id] = row.sku
            on_order_by_sku[row.sku_id] = row.on_order

        loc_by_sku: dict[uuid.UUID, list[LocationStock]] = {}
        for row in on_hand_rows:
            sku_by_id[row.sku_id] = row.sku
            loc_by_sku.setdefault(row.sku_id, []).append(row)

        if not sku_by_id:
            return []

        bin_rows = await self.bin_stock_crud.list_nonzero_for_skus(list(sku_by_id))
        bins_by_sku_location: dict[tuple[uuid.UUID, uuid.UUID], list[BinStock]] = {}
        for row in bin_rows:
            key = (row.sku_id, row.bin.location_id)
            bins_by_sku_location.setdefault(key, []).append(row)

        responses: list[InventorySkuResponse] = []
        for sku in sorted(sku_by_id.values(), key=lambda item: (item.our_ref, str(item.id))):
            loc_stocks = sorted(loc_by_sku.get(sku.id, []), key=lambda item: item.location.name)
            on_hand = sum(ls.on_hand for ls in loc_stocks)
            locations = [
                LocationStockResponse(
                    location_id=ls.location_id,
                    location_name=ls.location.name,
                    on_hand=ls.on_hand,
                    unit_cost_zar=None if hide_cost else ls.unit_cost_zar,
                    bins=[
                        BinOnHandResponse(
                            bin_id=bin_row.bin_id,
                            code=bin_row.bin.code,
                            on_hand=bin_row.on_hand,
                        )
                        for bin_row in sorted(
                            bins_by_sku_location.get((sku.id, ls.location_id), []),
                            key=lambda item: item.bin.code,
                        )
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
                    on_order=on_order_by_sku.get(sku.id, 0),
                    on_hand=on_hand,
                    sellable=on_hand > 0,
                    unit_cost_zar=unit_cost,
                    locations=locations,
                )
            )
        return responses

    async def unit_costs_by_sku_id(
        self,
        sku_ids: list[uuid.UUID],
        user_id: Optional[uuid.UUID] = None,
    ) -> dict[uuid.UUID, Optional[Decimal]]:
        if not sku_ids:
            return {}
        if await self._hide_cost(user_id):
            return {sku_id: None for sku_id in sku_ids}
        pairs = await self.location_stock_crud.on_hand_cost_pairs(sku_ids)
        return {sku_id: sku_level_unit_cost(pairs.get(sku_id, [])) for sku_id in sku_ids}

    async def get_at_location(
        self,
        sku_ref: str,
        location_name: str,
        user_id: uuid.UUID,
    ) -> dict[str, object]:
        sku = await self._resolve_sku(sku_ref)
        if sku is None:
            return {"error": f"SKU not found: {sku_ref}"}

        from app.crud.location import LocationCRUD

        location = await LocationCRUD(self.db).get_active_by_name_insensitive(location_name)
        if location is None:
            return {"error": f"Location not found: {location_name}"}

        row = await self.location_stock_crud.get_by_sku_and_location(sku.id, location.id)
        on_hand = row.on_hand if row is not None else 0
        hide_cost = not await PermissionService(self.db).has_permission(user_id, STOCK_COST_VIEW)

        payload: dict[str, object] = {
            "sku_id": str(sku.id),
            "our_ref": sku.our_ref,
            "location": location.name,
            "on_hand": on_hand,
        }
        if not hide_cost and row is not None:
            payload["unit_cost_zar"] = (
                str(row.unit_cost_zar) if row.unit_cost_zar is not None else None
            )
        return payload

    async def _hide_cost(self, user_id: Optional[uuid.UUID]) -> bool:
        if user_id is None:
            return True
        return not await PermissionService(self.db).has_permission(user_id, STOCK_COST_VIEW)

    async def _resolve_sku(self, sku_ref: str) -> Optional[Sku]:
        ref = sku_ref.strip()
        sku_crud = SkuCRUD(self.db)
        try:
            sku_id = uuid.UUID(ref)
        except ValueError:
            return await sku_crud.get_by_our_ref(ref)
        return await sku_crud.get_by_id(sku_id)
