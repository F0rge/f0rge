from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import BaseCRUD
from app.models.platform_meal import PlatformMeal


class PlatformMealCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _active_stmt(self, *, q: Optional[str] = None, cuisine: Optional[str] = None):
        stmt = (
            select(PlatformMeal)
            .where(PlatformMeal.is_active.is_(True))
            .options(selectinload(PlatformMeal.ingredients))
            .order_by(PlatformMeal.sort_order.asc(), PlatformMeal.id.asc())
        )
        if cuisine:
            stmt = stmt.where(PlatformMeal.cuisine == cuisine)
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    PlatformMeal.name.ilike(pattern),
                    PlatformMeal.slug.ilike(pattern),
                )
            )
        return stmt

    async def list_active(
        self,
        *,
        q: Optional[str] = None,
        cuisine: Optional[str] = None,
    ) -> list[PlatformMeal]:
        return list(
            (await self.db.execute(self._active_stmt(q=q, cuisine=cuisine))).scalars().all()
        )

    async def list_cuisines(self) -> list[str]:
        stmt = (
            select(PlatformMeal.cuisine)
            .where(PlatformMeal.is_active.is_(True))
            .distinct()
            .order_by(PlatformMeal.cuisine.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_id(self, platform_meal_id: int) -> Optional[PlatformMeal]:
        stmt = (
            select(PlatformMeal)
            .where(PlatformMeal.id == platform_meal_id, PlatformMeal.is_active.is_(True))
            .options(selectinload(PlatformMeal.ingredients))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
