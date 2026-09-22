from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.price_list import PriceList, PriceListItem
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import BaseCRUD


class PriceListCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, price_list_id: uuid.UUID) -> PriceList:
        result = await self.db.execute(
            select(PriceList)
            .options(selectinload(PriceList.items).selectinload(PriceListItem.sku))
            .where(PriceList.id == price_list_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Price list not found")
        return row

    async def get_by_name(self, name: str) -> Optional[PriceList]:
        result = await self.db.execute(select(PriceList).where(PriceList.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[PriceList]:
        result = await self.db.execute(
            select(PriceList)
            .options(selectinload(PriceList.items).selectinload(PriceListItem.sku))
            .order_by(PriceList.name)
        )
        return list(result.scalars().all())

    async def get_item(
        self,
        price_list_id: uuid.UUID,
        sku_id: uuid.UUID,
    ) -> Optional[PriceListItem]:
        result = await self.db.execute(
            select(PriceListItem).where(
                PriceListItem.price_list_id == price_list_id,
                PriceListItem.sku_id == sku_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_item_price(
        self,
        price_list_id: uuid.UUID,
        sku_id: uuid.UUID,
    ) -> Optional[Decimal]:
        item = await self.get_item(price_list_id, sku_id)
        if item is None:
            return None
        return item.unit_ex_vat
