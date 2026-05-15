from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias

logger = logging.getLogger(__name__)


_PLANT_QUALIFIERS = frozenset({
    "coconut", "oat", "almond", "soy", "soya", "rice", "cashew",
    "hemp", "peanut", "hazelnut", "macadamia", "pistachio",
    "sunflower", "flax", "walnut", "pecan", "sesame", "cocoa",
})

_DAIRY_HEAD_NOUNS = frozenset({
    "milk", "cream", "butter", "cheese", "yogurt", "yoghurt", "kefir",
})


class IngredientLookupService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def lookup(self, name: str) -> Optional[DietaryIngredient]:
        """Match an ingredient name to the dietary reference DB.

        Chain: exact canonical -> alias -> head-noun (last word) ->
        case-insensitive LIKE.
        """
        normalised = name.lower().strip()
        if not normalised:
            return None

        # 1. Exact match on canonical_name
        result = (
            self.db.query(DietaryIngredient)
            .filter(DietaryIngredient.canonical_name == normalised)
            .first()
        )
        if result:
            return result

        # 2. Alias lookup
        alias = (
            self.db.query(IngredientAlias)
            .filter(IngredientAlias.alias == normalised)
            .first()
        )
        if alias:
            return (
                self.db.query(DietaryIngredient)
                .filter(DietaryIngredient.canonical_name == alias.canonical_name)
                .first()
            )

        # 3. Head-noun fallback: for English compound food names, the last
        # word is usually the base ingredient (cherry tomato -> tomato,
        # wheat flour -> flour, fresh basil -> basil). Try the last word
        # as an exact canonical/alias match before the loose LIKE fallback.
        #
        # Guard: skip when a plant-based qualifier precedes a dairy head
        # noun (e.g. "coconut milk", "oat cream") to avoid false allergen
        # inheritance. No data is better than wrong data.
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
                    self.db.query(DietaryIngredient)
                    .filter(DietaryIngredient.canonical_name == last_word)
                    .first()
                )
                if result:
                    return result
                alias = (
                    self.db.query(IngredientAlias)
                    .filter(IngredientAlias.alias == last_word)
                    .first()
                )
                if alias:
                    return (
                        self.db.query(DietaryIngredient)
                        .filter(DietaryIngredient.canonical_name == alias.canonical_name)
                        .first()
                    )

        # 4. Case-insensitive LIKE on full search term
        return (
            self.db.query(DietaryIngredient)
            .filter(DietaryIngredient.canonical_name.ilike(f"%{normalised}%"))
            .first()
        )

    def lookup_batch(self, names: list[str]) -> dict[str, Optional[DietaryIngredient]]:
        """Batch lookup for multiple ingredient names."""
        return {name: self.lookup(name) for name in names}

    def suggest_canonical(self, name: str, limit: int = 5) -> list[DietaryIngredient]:
        """Return top matching dietary ingredients for autocomplete."""
        normalised = name.lower().strip()
        return (
            self.db.query(DietaryIngredient)
            .filter(DietaryIngredient.canonical_name.ilike(f"%{normalised}%"))
            .limit(limit)
            .all()
        )
