"""Load SIGHI histamine compatibility data into dietary_ingredients."""

from __future__ import annotations

import json
import logging

from scripts._db import SyncSession
from scripts._paths import data_dir

from app.models.dietary_ingredient import DietaryIngredient  # noqa: F401 (ensures Base is populated)
from app.database import Base  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DATA_PATH = data_dir() / "sighi_histamine.json"


def load() -> None:
    log.info("Loading SIGHI histamine data from %s", DATA_PATH)

    with open(DATA_PATH) as f:
        items: list[dict] = json.load(f)

    inserted = 0
    updated = 0

    with SyncSession() as session:
        for item in items:
            name = item["name"].strip().lower()
            category = item.get("category", "").strip().lower() or None
            score = item["score"]

            existing = (
                session.query(DietaryIngredient)
                .filter_by(canonical_name=name)
                .first()
            )

            if existing:
                if category is not None:
                    existing.category = category
                existing.histamine_score = score
                existing.source = "sighi"
                existing.source_version = "2024"
                updated += 1
            else:
                session.add(
                    DietaryIngredient(
                        canonical_name=name,
                        category=category,
                        histamine_score=score,
                        source="sighi",
                        source_version="2024",
                        contains_gluten=False,
                        contains_dairy=False,
                    )
                )
                inserted += 1

    log.info(
        "SIGHI load complete: %d inserted, %d updated, %d total processed",
        inserted,
        updated,
        len(items),
    )


if __name__ == "__main__":
    load()
