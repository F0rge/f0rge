from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.tenant import owned_by_user


class IngredientLookupCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_canonical(self, canonical_name: str) -> Optional[DietaryIngredient]:
        stmt = select(DietaryIngredient).where(
            owned_by_user(DietaryIngredient.user_id),
            DietaryIngredient.canonical_name == canonical_name,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_alias(self, alias: str) -> Optional[IngredientAlias]:
        stmt = select(IngredientAlias).where(
            owned_by_user(IngredientAlias.user_id), IngredientAlias.alias == alias
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_best_ilike_match(self, term: str) -> Optional[DietaryIngredient]:
        """Loose substring match, shortest (most general) canonical_name wins."""
        stmt = (
            select(DietaryIngredient)
            .where(
                owned_by_user(DietaryIngredient.user_id),
                DietaryIngredient.canonical_name.ilike(f"%{term}%"),
            )
            .order_by(func.length(DietaryIngredient.canonical_name))
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def suggest(self, term: str, limit: int) -> list[DietaryIngredient]:
        stmt = (
            select(DietaryIngredient)
            .where(
                owned_by_user(DietaryIngredient.user_id),
                DietaryIngredient.canonical_name.ilike(f"%{term}%"),
            )
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())
