from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias

logger = logging.getLogger(__name__)


class IngredientLookupService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def lookup(self, name: str) -> Optional[DietaryIngredient]:
        """Match an ingredient name to the dietary reference DB.

        Chain: exact canonical -> alias -> case-insensitive LIKE.
        """
        normalised = name.lower().strip()

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

        # 3. Case-insensitive LIKE
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
