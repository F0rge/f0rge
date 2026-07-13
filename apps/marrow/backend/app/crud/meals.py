from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.meal import Meal
from app.models.meal_tag import MealTag
from app.models.photo import Photo


class MealCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, meal_id: int) -> Optional[Meal]:
        return await self.db.get(Meal, meal_id)

    async def add_and_flush(self, meal: Meal) -> Meal:
        self.db.add(meal)
        await self.db.flush()
        return meal

    async def delete_if_orphaned(self, meal_id: int) -> bool:
        """Delete the meal when no placements remain. Returns True if deleted."""
        count = (
            await self.db.execute(
                select(func.count()).select_from(Photo).where(Photo.meal_id == meal_id)
            )
        ).scalar_one()
        if count > 0:
            return False
        delivered_tags = (
            await self.db.execute(
                select(func.count())
                .select_from(MealTag)
                .where(
                    MealTag.source_meal_id == meal_id,
                    MealTag.status == "delivered",
                )
            )
        ).scalar_one()
        if delivered_tags > 0:
            return False
        meal = await self.get_by_id(meal_id)
        if meal is None:
            return False
        await self.db.delete(meal)
        await self.db.flush()
        return True
