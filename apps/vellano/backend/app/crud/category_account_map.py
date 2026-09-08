from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_account_map import CategoryAccountMap
from f0rge_db.crud import BaseCRUD


class CategoryAccountMapCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, map_id: uuid.UUID) -> Optional[CategoryAccountMap]:
        return (
            await self.db.execute(select(CategoryAccountMap).where(CategoryAccountMap.id == map_id))
        ).scalar_one_or_none()

    async def get_by_category_insensitive(self, category: str) -> Optional[CategoryAccountMap]:
        return (
            await self.db.execute(
                select(CategoryAccountMap).where(
                    func.lower(CategoryAccountMap.category) == category.lower()
                )
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[CategoryAccountMap]:
        result = await self.db.execute(
            select(CategoryAccountMap).order_by(CategoryAccountMap.category)
        )
        return list(result.scalars().all())
