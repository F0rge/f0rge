"""Load FODMAP data into dietary_ingredients."""

from __future__ import annotations

import json
import logging

from scripts._db import SyncSession
from scripts._paths import data_dir

from app.models.dietary_ingredient import DietaryIngredient  # noqa: F401
from app.database import Base  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DATA_PATH = data_dir() / "fodmap_list.json"


def load() -> None:
    log.info("Loading FODMAP data from %s", DATA_PATH)

    with open(DATA_PATH) as f:
        items: list[dict] = json.load(f)

    inserted = 0
    updated = 0

    with SyncSession() as session:
        for item in items:
            name = item["name"].strip().lower()
            oligos = item.get("oligos", "low")
            fructose = item.get("fructose", "low")
            polyols = item.get("polyols", "low")
            lactose = item.get("lactose", "low")

            existing = session.query(DietaryIngredient).filter_by(canonical_name=name).first()

            if existing:
                existing.fodmap_oligos = oligos
                existing.fodmap_fructose = fructose
                existing.fodmap_polyols = polyols
                existing.fodmap_lactose = lactose
                updated += 1
            else:
                session.add(
                    DietaryIngredient(
                        canonical_name=name,
                        fodmap_oligos=oligos,
                        fodmap_fructose=fructose,
                        fodmap_polyols=polyols,
                        fodmap_lactose=lactose,
                        contains_gluten=False,
                        contains_dairy=False,
                        source="monash",
                        source_version="2024",
                    )
                )
                inserted += 1

    log.info(
        "FODMAP load complete: %d inserted, %d updated, %d total processed",
        inserted,
        updated,
        len(items),
    )


if __name__ == "__main__":
    load()
