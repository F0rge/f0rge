from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.schemas.dietary_ingredient import (
    AliasCreate,
    DietaryIngredientCreate,
    DietaryIngredientUpdate,
)


class DietaryIngredientCatalogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_items(
        self, search: Optional[str] = None, include_archived: bool = False
    ) -> list[DietaryIngredient]:
        stmt = select(DietaryIngredient)
        if not include_archived:
            stmt = stmt.where(DietaryIngredient.archived.is_(False))
        if search:
            stmt = stmt.where(DietaryIngredient.canonical_name.ilike(f"%{search.strip().lower()}%"))
        stmt = stmt.order_by(DietaryIngredient.canonical_name.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get(self, ingredient_id: int) -> DietaryIngredient:
        item = (
            await self.db.execute(
                select(DietaryIngredient).where(DietaryIngredient.id == ingredient_id)
            )
        ).scalar_one_or_none()
        if item is None:
            raise NotFoundError(f"Dietary ingredient {ingredient_id} not found.")
        return item

    async def create_item(self, data: DietaryIngredientCreate) -> DietaryIngredient:
        normalized = data.canonical_name.strip().lower()
        if not normalized:
            raise ValidationError("canonical_name must not be blank.")
        payload = data.model_dump()
        payload["canonical_name"] = normalized

        existing = (
            await self.db.execute(
                select(DietaryIngredient).where(DietaryIngredient.canonical_name == normalized)
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.archived:
                for field, value in payload.items():
                    setattr(existing, field, value)
                existing.archived = False
                await self.db.commit()
                await self.db.refresh(existing)
                return existing
            raise ConflictError(f"Dietary ingredient '{normalized}' already exists.")

        item = DietaryIngredient(**payload)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update_item(
        self, ingredient_id: int, data: DietaryIngredientUpdate
    ) -> DietaryIngredient:
        item = await self.get(ingredient_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def set_archived(self, ingredient_id: int, archived: bool) -> DietaryIngredient:
        return await self.update_item(ingredient_id, DietaryIngredientUpdate(archived=archived))

    async def add_alias(self, ingredient_id: int, data: AliasCreate) -> IngredientAlias:
        ingredient = await self.get(ingredient_id)
        normalized_alias = data.alias.strip().lower()

        # No unique constraint on (alias, canonical_name) at the DB level, so
        # this is the guard. ingredient.aliases is eager-loaded (lazy="selectin"),
        # so scanning it in memory is equivalent to a SELECT NOT EXISTS check
        # with no extra round trip. A repeat call is idempotent -- it returns
        # the existing row rather than raising, since the caller's intent
        # ("this alias should exist") is already satisfied.
        existing = next((a for a in ingredient.aliases if a.alias == normalized_alias), None)
        if existing is not None:
            return existing

        # Append through the relationship (not a bare IngredientAlias(...) + db.add())
        # so the parent's already-loaded `aliases` collection stays in sync --
        # otherwise a second read within the same session sees a stale empty list.
        alias = IngredientAlias(alias=normalized_alias, language=data.language)
        ingredient.aliases.append(alias)
        await self.db.commit()
        await self.db.refresh(alias)
        return alias

    async def remove_alias(self, alias_id: int) -> None:
        alias = (
            await self.db.execute(select(IngredientAlias).where(IngredientAlias.id == alias_id))
        ).scalar_one_or_none()
        if alias is None:
            raise NotFoundError(f"Alias {alias_id} not found.")
        # Remove through the relationship (cascade="all, delete-orphan" on
        # DietaryIngredient.aliases deletes the orphaned row on flush) so the
        # parent's in-memory collection stays consistent, same reasoning as add_alias.
        alias.ingredient.aliases.remove(alias)
        await self.db.commit()
