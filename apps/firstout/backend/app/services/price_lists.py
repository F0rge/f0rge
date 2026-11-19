from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.price_list import PriceListCRUD
from app.crud.sku import SkuCRUD
from app.models.price_list import PriceList, PriceListItem
from app.schemas.price_list import (
    PriceListCreate,
    PriceListItemResponse,
    PriceListItemUpsert,
    PriceListResponse,
    PriceListUpdate,
)
from app.services.suspect_price import average_costs_by_sku_id, is_below_average_cost
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class PriceListService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = PriceListCRUD(db)
        self.sku_crud = SkuCRUD(db)

    async def list(self, archived: Optional[bool] = False) -> list[PriceListResponse]:
        rows = [
            row
            for row in await self.crud.list_all()
            if archived is None or row.is_archived == archived
        ]
        costs = await self._costs_for(rows)
        return [self._to_response(row, costs) for row in rows]

    async def set_archived(self, price_list_id: uuid.UUID, is_archived: bool) -> PriceListResponse:
        row = await self.crud.get_by_id(price_list_id, for_update=True)
        row.is_archived = is_archived
        await self.crud.commit_refresh(row)
        return await self.get(price_list_id)

    async def get(self, price_list_id: uuid.UUID) -> PriceListResponse:
        row = await self.crud.get_by_id(price_list_id)
        costs = await self._costs_for([row])
        return self._to_response(row, costs)

    async def create(self, data: PriceListCreate) -> PriceListResponse:
        existing = await self.crud.get_by_name(data.name)
        if existing is not None:
            raise ConflictError("A price list with this name already exists")
        self._validate_till_policy(data.name, data.till_require_listed_price)
        row = PriceList(name=data.name, till_require_listed_price=data.till_require_listed_price)
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(row)
            try:
                await self.crud.commit_refresh(row)
            except IntegrityError as exc:
                raise ConflictError("A price list with this name already exists") from exc
        return await self.get(row.id)

    async def update(self, price_list_id: uuid.UUID, data: PriceListUpdate) -> PriceListResponse:
        row = await self.crud.get_by_id(price_list_id)
        self._require_active(row)
        other = await self.crud.get_by_name(data.name)
        if other is not None and other.id != price_list_id:
            raise ConflictError("A price list with this name already exists")
        required = (
            row.till_require_listed_price
            if data.till_require_listed_price is None
            else data.till_require_listed_price
        )
        self._validate_till_policy(data.name, required)
        row.name = data.name
        row.till_require_listed_price = required
        async with unit_of_work(self.db):
            try:
                await self.crud.commit_refresh(row)
            except IntegrityError as exc:
                raise ConflictError("A price list with this name already exists") from exc
        return await self.get(price_list_id)

    async def delete(self, price_list_id: uuid.UUID) -> None:
        # Customer assignment takes this same lock until its write commits.
        row = await self.crud.get_by_id(price_list_id, for_update=True)
        if await self.crud.has_customer_assignments(price_list_id):
            raise ConflictError("This price list is assigned to customers; archive it instead")
        async with unit_of_work(self.db):
            await self.db.delete(row)

    async def upsert_item(
        self,
        price_list_id: uuid.UUID,
        data: PriceListItemUpsert,
    ) -> PriceListResponse:
        self._require_active(await self.crud.get_by_id(price_list_id))
        sku = await self.sku_crud.get_by_id(data.sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        item = await self.crud.get_item(price_list_id, data.sku_id)
        async with unit_of_work(self.db):
            if item is None:
                item = PriceListItem(
                    price_list_id=price_list_id,
                    sku_id=data.sku_id,
                    unit_ex_vat=data.unit_ex_vat,
                )
                await self.crud.add_and_flush(item)
            else:
                item.unit_ex_vat = data.unit_ex_vat
        return await self.get(price_list_id)

    async def delete_item(self, price_list_id: uuid.UUID, sku_id: uuid.UUID) -> PriceListResponse:
        self._require_active(await self.crud.get_by_id(price_list_id))
        item = await self.crud.get_item(price_list_id, sku_id)
        if item is None:
            raise NotFoundError("Price list item not found")
        async with unit_of_work(self.db):
            await self.db.delete(item)
        return await self.get(price_list_id)

    async def _costs_for(self, rows: list[PriceList]) -> dict[uuid.UUID, Optional[Decimal]]:
        sku_ids = [item.sku_id for row in rows for item in row.items]
        return await average_costs_by_sku_id(self.db, sku_ids)

    def _to_response(
        self,
        row: PriceList,
        costs: dict[uuid.UUID, Optional[Decimal]],
    ) -> PriceListResponse:
        items = [
            PriceListItemResponse(
                sku_id=item.sku_id,
                our_ref=item.sku.our_ref,
                unit_ex_vat=item.unit_ex_vat,
                below_average_cost=is_below_average_cost(item.unit_ex_vat, costs.get(item.sku_id)),
            )
            for item in row.items
        ]
        return PriceListResponse(
            id=row.id,
            name=row.name,
            is_archived=row.is_archived,
            till_require_listed_price=row.till_require_listed_price,
            items=items,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _validate_till_policy(name: str, required: bool) -> None:
        # Imported lists have a different pricing contract. The checkout policy
        # can only be enabled on a reviewed, staff-managed list.
        from app.services.pricing import is_cin7_generated_price_list

        if required and is_cin7_generated_price_list(name):
            raise ConflictError(
                "Use a staff-managed price list to require listed prices at the till"
            )

    @staticmethod
    def _require_active(row: PriceList) -> None:
        if row.is_archived:
            raise ConflictError("Restore the price list before editing its prices")
