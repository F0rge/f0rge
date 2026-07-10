from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ingredient_lookup import IngredientLookupCRUD
from app.models.dietary_ingredient import DietaryIngredient

logger = logging.getLogger(__name__)


_PLANT_QUALIFIERS = frozenset(
    {
        "coconut",
        "oat",
        "almond",
        "soy",
        "soya",
        "rice",
        "cashew",
        "hemp",
        "peanut",
        "hazelnut",
        "macadamia",
        "pistachio",
        "sunflower",
        "flax",
        "walnut",
        "pecan",
        "sesame",
        "cocoa",
    }
)

_DAIRY_HEAD_NOUNS = frozenset(
    {
        "milk",
        "cream",
        "butter",
        "cheese",
        "yogurt",
        "yoghurt",
        "kefir",
    }
)


class IngredientLookupService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = IngredientLookupCRUD(db)

    async def lookup(self, name: str) -> Optional[DietaryIngredient]:
        """Match an ingredient name to the dietary reference DB.

        Chain: exact canonical -> alias -> head-noun (last word) ->
        case-insensitive LIKE.
        """
        normalised = name.lower().strip()
        if not normalised:
            return None

        # 1. Exact match on canonical_name
        result = await self.crud.get_by_canonical(normalised)
        if result:
            return result

        # 2. Alias lookup
        alias = await self.crud.get_alias(normalised)
        if alias:
            return await self.crud.get_by_canonical(alias.canonical_name)

        # 3. Head-noun fallback
        words = normalised.split()
        if len(words) > 1:
            last_word = words[-1]
            qualifiers = set(words[:-1])
            if last_word in _DAIRY_HEAD_NOUNS and qualifiers & _PLANT_QUALIFIERS:
                logger.debug(
                    "Skipping head-noun fallback for '%s' (plant-based qualifier)",
                    normalised,
                )
            else:
                result = await self.crud.get_by_canonical(last_word)
                if result:
                    return result
                alias = await self.crud.get_alias(last_word)
                if alias:
                    return await self.crud.get_by_canonical(alias.canonical_name)

        # 4. Case-insensitive LIKE on full search term. This is a fuzzy
        # fallback (e.g. vision returns "cheese" -> matches many cheese
        # variants). Order by canonical_name length so the shortest /
        # most general match wins, and use .first() since the query is
        # explicitly allowed to match multiple rows.
        return await self.crud.find_best_ilike_match(normalised)

    async def lookup_batch(self, names: list[str]) -> dict[str, Optional[DietaryIngredient]]:
        """Batch lookup for multiple ingredient names."""
        result = {}
        for name in names:
            result[name] = await self.lookup(name)
        return result

    async def suggest_canonical(self, name: str, limit: int = 5) -> list[DietaryIngredient]:
        """Return top matching dietary ingredients for autocomplete."""
        normalised = name.lower().strip()
        return await self.crud.suggest(normalised, limit)
