from __future__ import annotations

import uuid

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
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class PriceListService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = PriceListCRUD(db)
        self.sku_crud = SkuCRUD(db)

    async def list(self) -> list[PriceListResponse]:
        rows = await self.crud.list_all()
        return [self._to_response(row) for row in rows]

    async def get(self, price_list_id: uuid.UUID) -> PriceListResponse:
        row = await self.crud.get_by_id(price_list_id)
        return self._to_response(row)

    async def create(self, data: PriceListCreate) -> PriceListResponse:
        existing = await self.crud.get_by_name(data.name)
        if existing is not None:
            raise ConflictError("A price list with this name already exists")
        row = PriceList(name=data.name)
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(row)
            try:
                await self.crud.commit_refresh(row)
            except IntegrityError as exc:
                raise ConflictError("A price list with this name already exists") from exc
        return await self.get(row.id)

    async def update(self, price_list_id: uuid.UUID, data: PriceListUpdate) -> PriceListResponse:
        row = await self.crud.get_by_id(price_list_id)
        other = await self.crud.get_by_name(data.name)
        if other is not None and other.id != price_list_id:
            raise ConflictError("A price list with this name already exists")
        row.name = data.name
        async with unit_of_work(self.db):
            try:
                await self.crud.commit_refresh(row)
            except IntegrityError as exc:
                raise ConflictError("A price list with this name already exists") from exc
        return await self.get(price_list_id)

    async def delete(self, price_list_id: uuid.UUID) -> None:
        row = await self.crud.get_by_id(price_list_id)
        async with unit_of_work(self.db):
            await self.db.delete(row)

    async def upsert_item(
        self,
        price_list_id: uuid.UUID,
        data: PriceListItemUpsert,
    ) -> PriceListResponse:
        await self.crud.get_by_id(price_list_id)
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
        await self.crud.get_by_id(price_list_id)
        item = await self.crud.get_item(price_list_id, sku_id)
        if item is None:
            raise NotFoundError("Price list item not found")
        async with unit_of_work(self.db):
            await self.db.delete(item)
        return await self.get(price_list_id)

    def _to_response(self, row: PriceList) -> PriceListResponse:
        items = [
            PriceListItemResponse(
                sku_id=item.sku_id,
                our_ref=item.sku.our_ref,
                unit_ex_vat=item.unit_ex_vat,
            )
            for item in row.items
        ]
        return PriceListResponse(
            id=row.id,
            name=row.name,
            items=items,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
