from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias

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

    async def lookup(self, name: str) -> Optional[DietaryIngredient]:
        """Match an ingredient name to the dietary reference DB.

        Chain: exact canonical -> alias -> head-noun (last word) ->
        case-insensitive LIKE.
        """
        normalised = name.lower().strip()
        if not normalised:
            return None

        # 1. Exact match on canonical_name
        result = (
            await self.db.execute(
                select(DietaryIngredient).where(
                    DietaryIngredient.canonical_name == normalised
                )
            )
        ).scalar_one_or_none()
        if result:
            return result

        # 2. Alias lookup
        alias = (
            await self.db.execute(
                select(IngredientAlias).where(IngredientAlias.alias == normalised)
            )
        ).scalar_one_or_none()
        if alias:
            return (
                await self.db.execute(
                    select(DietaryIngredient).where(
                        DietaryIngredient.canonical_name == alias.canonical_name
                    )
                )
            ).scalar_one_or_none()

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
                result = (
                    await self.db.execute(
                        select(DietaryIngredient).where(
                            DietaryIngredient.canonical_name == last_word
                        )
                    )
                ).scalar_one_or_none()
                if result:
                    return result
                alias = (
                    await self.db.execute(
                        select(IngredientAlias).where(
                            IngredientAlias.alias == last_word
                        )
                    )
                ).scalar_one_or_none()
                if alias:
                    return (
                        await self.db.execute(
                            select(DietaryIngredient).where(
                                DietaryIngredient.canonical_name == alias.canonical_name
                            )
                        )
                    ).scalar_one_or_none()

        # 4. Case-insensitive LIKE on full search term
        return (
            await self.db.execute(
                select(DietaryIngredient).where(
                    DietaryIngredient.canonical_name.ilike(f"%{normalised}%")
                )
            )
        ).scalar_one_or_none()

    async def lookup_batch(
        self, names: list[str]
    ) -> dict[str, Optional[DietaryIngredient]]:
        """Batch lookup for multiple ingredient names."""
        result = {}
        for name in names:
            result[name] = await self.lookup(name)
        return result

    async def suggest_canonical(
        self, name: str, limit: int = 5
    ) -> list[DietaryIngredient]:
        """Return top matching dietary ingredients for autocomplete."""
        normalised = name.lower().strip()
        return list(
            (
                await self.db.execute(
                    select(DietaryIngredient)
                    .where(DietaryIngredient.canonical_name.ilike(f"%{normalised}%"))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
