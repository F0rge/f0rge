"""Load user-curated dietary ingredients + aliases into the reference tables.

Unlike the SIGHI/FODMAP/allergen loaders (each of which fills only its slice
of a row), the curated file carries every catalogue column for each row, so a
single upsert here fully populates the ingredient. Runs LAST in the seed
orchestrator (after build_aliases rebuilds the alias table) so the aliases it
inserts survive that rebuild.

Source files (loaded in order; later files only add rows, same format):
  backend/data/curated_ingredients_2026_07.json
  backend/data/curated_ingredients_2026_09.json   (muesli, flour, bread, pasta, cocoa)
  { "source", "source_version", "ingredients": [...], "aliases": [...] }
Aliases may carry an optional "language" (default "en").
The per-row "confidence" key is provenance only and is ignored here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from scripts._db import SyncSession
from scripts._paths import data_dir

from app.models.dietary_ingredient import DietaryIngredient  # noqa: F401
from app.models.ingredient_alias import IngredientAlias  # noqa: F401
from app.database import Base  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CURATED_FILES = (
    "curated_ingredients_2026_07.json",
    "curated_ingredients_2026_09.json",
)
DATA_PATHS = tuple(data_dir() / name for name in CURATED_FILES)

_COLS = (
    "category",
    "histamine_score",
    "fodmap_oligos",
    "fodmap_fructose",
    "fodmap_polyols",
    "fodmap_lactose",
    "contains_gluten",
    "contains_dairy",
)


def load() -> None:
    for path in DATA_PATHS:
        _load_file(path)


def _load_file(path: Path) -> None:
    log.info("Loading curated ingredients from %s", path)

    with open(path) as f:
        payload = json.load(f)

    source = payload.get("source", "user-research-2026-07")
    source_version = payload.get("source_version")
    ingredients: list[dict] = payload["ingredients"]
    aliases: list[dict] = payload.get("aliases", [])

    ing_inserted = ing_updated = 0
    ali_inserted = ali_skipped = 0

    with SyncSession() as session:
        for item in ingredients:
            name = item["canonical_name"].strip().lower()
            values = {c: item[c] for c in _COLS}

            existing = session.query(DietaryIngredient).filter_by(canonical_name=name).first()
            if existing:
                for col, val in values.items():
                    setattr(existing, col, val)
                existing.source = source
                existing.source_version = source_version
                ing_updated += 1
            else:
                session.add(
                    DietaryIngredient(
                        canonical_name=name,
                        source=source,
                        source_version=source_version,
                        **values,
                    )
                )
                ing_inserted += 1

        session.flush()  # canonical rows must exist before alias FK insert

        seen: set[tuple[str, str]] = set()
        for a in aliases:
            alias = a["alias"].strip().lower()
            canonical = a["canonical_name"].strip().lower()
            key = (alias, canonical)
            if key in seen:
                continue
            seen.add(key)

            if not session.query(DietaryIngredient).filter_by(canonical_name=canonical).first():
                log.debug("Skipping alias '%s' -> '%s': canonical not found", alias, canonical)
                ali_skipped += 1
                continue
            already = (
                session.query(IngredientAlias)
                .filter_by(alias=alias, canonical_name=canonical)
                .first()
            )
            if already:
                ali_skipped += 1
                continue
            session.add(
                IngredientAlias(
                    alias=alias, canonical_name=canonical, language=a.get("language") or "en"
                )
            )
            ali_inserted += 1

    log.info(
        "Curated load complete: ingredients %d inserted / %d updated; aliases %d inserted / %d skipped",
        ing_inserted,
        ing_updated,
        ali_inserted,
        ali_skipped,
    )


if __name__ == "__main__":
    load()
