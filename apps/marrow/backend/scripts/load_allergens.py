"""Load allergen (gluten/dairy) flags into dietary_ingredients."""

from __future__ import annotations

import json
import logging

from scripts._db import SyncSession
from scripts._paths import data_dir

from app.models.dietary_ingredient import DietaryIngredient  # noqa: F401
from app.database import Base  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DATA_PATH = data_dir() / "allergens.json"


def load() -> None:
    log.info("Loading allergen data from %s", DATA_PATH)

    with open(DATA_PATH) as f:
        items: list[dict] = json.load(f)

    inserted = 0
    updated = 0

    with SyncSession() as session:
        for item in items:
            name = item["name"].strip().lower()
            gluten = bool(item.get("contains_gluten", False))
            dairy = bool(item.get("contains_dairy", False))

            existing = session.query(DietaryIngredient).filter_by(canonical_name=name).first()

            if existing:
                existing.contains_gluten = gluten
                existing.contains_dairy = dairy
                existing.source = existing.source or "allergens"
                existing.source_version = existing.source_version or "2024"
                updated += 1
            else:
                session.add(
                    DietaryIngredient(
                        canonical_name=name,
                        contains_gluten=gluten,
                        contains_dairy=dairy,
                        source="allergens",
                        source_version="2024",
                    )
                )
                inserted += 1

    log.info(
        "Allergen load complete: %d inserted, %d updated, %d total processed",
        inserted,
        updated,
        len(items),
    )


if __name__ == "__main__":
    load()
