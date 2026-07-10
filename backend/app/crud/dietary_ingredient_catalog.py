from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias

CATALOG_SEARCH_LIMIT = 50


class DietaryIngredientCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list(
        self,
        search: Optional[str] = None,
        include_archived: bool = False,
        limit: Optional[int] = None,
    ) -> list[DietaryIngredient]:
        stmt = select(DietaryIngredient)
        if not include_archived:
            stmt = stmt.where(DietaryIngredient.archived.is_(False))
        if search:
            term = search.strip().lower()
            stmt = stmt.outerjoin(
                IngredientAlias,
                DietaryIngredient.canonical_name == IngredientAlias.canonical_name,
            ).where(
                or_(
                    DietaryIngredient.canonical_name.ilike(f"%{term}%"),
                    IngredientAlias.alias.ilike(f"%{term}%"),
                )
            )
            stmt = stmt.distinct()
            if limit is None:
                limit = CATALOG_SEARCH_LIMIT
        stmt = stmt.order_by(DietaryIngredient.canonical_name.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_id(self, ingredient_id: int) -> Optional[DietaryIngredient]:
        stmt = select(DietaryIngredient).where(DietaryIngredient.id == ingredient_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_canonical_name(self, canonical_name: str) -> Optional[DietaryIngredient]:
        stmt = select(DietaryIngredient).where(DietaryIngredient.canonical_name == canonical_name)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_alias_by_id(self, alias_id: int) -> Optional[IngredientAlias]:
        stmt = select(IngredientAlias).where(IngredientAlias.id == alias_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
