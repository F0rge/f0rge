from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.dietary_ingredient_catalog import DietaryIngredientCRUD
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.schemas.dietary_ingredient import (
    AliasCreate,
    DietaryIngredientCreate,
    DietaryIngredientUpdate,
)
from f0rge_db.tenant import current_user_id


class DietaryIngredientCatalogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = DietaryIngredientCRUD(db)

    async def list_items(
        self,
        search: Optional[str] = None,
        include_archived: bool = False,
        limit: Optional[int] = None,
    ) -> list[DietaryIngredient]:
        return await self.crud.list(search, include_archived, limit)

    async def get(self, ingredient_id: int) -> DietaryIngredient:
        item = await self.crud.get_by_id(ingredient_id)
        if item is None:
            raise NotFoundError(f"Dietary ingredient {ingredient_id} not found.")
        return item

    async def create_item(self, data: DietaryIngredientCreate) -> DietaryIngredient:
        normalized = data.canonical_name.strip().lower()
        if not normalized:
            raise ValidationError("canonical_name must not be blank.")
        payload = data.model_dump()
        payload["canonical_name"] = normalized

        existing = await self.crud.get_by_canonical_name(normalized)
        if existing is not None:
            if existing.archived:
                for field, value in payload.items():
                    setattr(existing, field, value)
                existing.archived = False
                return await self.crud.commit_refresh(existing)
            raise ConflictError(f"Dietary ingredient '{normalized}' already exists.")

        item = DietaryIngredient(**payload, user_id=current_user_id())
        self.crud.add(item)
        return await self.crud.commit_refresh(item)

    async def update_item(
        self, ingredient_id: int, data: DietaryIngredientUpdate
    ) -> DietaryIngredient:
        item = await self.get(ingredient_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        return await self.crud.commit_refresh(item)

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
        alias = IngredientAlias(
            alias=normalized_alias,
            language=data.language,
            user_id=ingredient.user_id,
            canonical_name=ingredient.canonical_name,
        )
        ingredient.aliases.append(alias)
        return await self.crud.commit_refresh(alias)

    async def remove_alias(self, alias_id: int) -> None:
        alias = await self.crud.get_alias_by_id(alias_id)
        if alias is None:
            raise NotFoundError(f"Alias {alias_id} not found.")
        # Delete the already-fetched row directly. Going through the parent
        # relationship (alias.ingredient.aliases.remove(alias)) would touch
        # alias.ingredient.aliases, which is unloaded when the alias is fetched
        # cold by id -- accessing it lazy-loads in the async session and raises
        # MissingGreenlet. The parent's in-memory collection consistency is
        # irrelevant here: the row is deleted and the endpoint returns 204.
        await self.crud.delete_and_commit(alias)
