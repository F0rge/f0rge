from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku_bom_line import SkuBomLine
from f0rge_db.crud import BaseCRUD


class SkuBomLineCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_by_parent(self, parent_sku_id: uuid.UUID) -> list[SkuBomLine]:
        result = await self.db.execute(
            select(SkuBomLine)
            .where(SkuBomLine.parent_sku_id == parent_sku_id)
            .order_by(SkuBomLine.created_at, SkuBomLine.id)
        )
        return list(result.scalars().all())

    async def delete_for_parent(self, parent_sku_id: uuid.UUID) -> None:
        await self.db.execute(delete(SkuBomLine).where(SkuBomLine.parent_sku_id == parent_sku_id))

    async def parent_ids_with_bom(self, sku_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not sku_ids:
            return set()
        result = await self.db.execute(
            select(SkuBomLine.parent_sku_id).where(SkuBomLine.parent_sku_id.in_(sku_ids)).distinct()
        )
        return set(result.scalars().all())
