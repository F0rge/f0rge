"""Backfill the 18 curated ingredients + aliases into an ALREADY-seeded DB.

The lifespan seed (`_seed_dietary_db_if_empty`) only runs on an empty
`dietary_ingredients` table, so existing dev/prod volumes never pick up rows
added to the seed source. This script closes that gap: it inserts the curated
rows and aliases that are missing, and leaves everything else untouched.

Idempotent — safe to run repeatedly:
  * ingredients: inserted only if `canonical_name` is absent (never updates an
    existing row, so it won't clobber a manually-curated classification);
  * aliases: inserted only if the exact (alias, canonical_name) pair is absent
    (the table has no unique constraint, so we must check the pair ourselves).

Source of truth is the same file the fresh-seed loader reads:
  backend/data/curated_ingredients_2026_07.json

Usage:
    cd backend && uv run python -m scripts.backfill_missing_ingredients_2026_07
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.database import async_session_maker
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "curated_ingredients_2026_07.json"

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


async def backfill() -> dict[str, int]:
    payload = json.loads(DATA_PATH.read_text())
    source = payload.get("source", "user-research-2026-07")
    source_version = payload.get("source_version")
    ingredients: list[dict] = payload["ingredients"]
    aliases: list[dict] = payload.get("aliases", [])

    ing_inserted = ing_skipped = 0
    ali_inserted = ali_skipped = 0

    async with async_session_maker() as session:
        existing_names = set(
            (await session.execute(select(DietaryIngredient.canonical_name))).scalars().all()
        )

        for item in ingredients:
            name = item["canonical_name"].strip().lower()
            if name in existing_names:
                ing_skipped += 1
                continue
            session.add(
                DietaryIngredient(
                    canonical_name=name,
                    source=source,
                    source_version=source_version,
                    **{c: item[c] for c in _COLS},
                )
            )
            existing_names.add(name)
            ing_inserted += 1

        # Flush so newly-inserted canonicals satisfy the alias FK below.
        await session.flush()

        existing_pairs = set(
            (
                await session.execute(select(IngredientAlias.alias, IngredientAlias.canonical_name))
            ).all()
        )
        for a in aliases:
            alias = a["alias"].strip().lower()
            canonical = a["canonical_name"].strip().lower()
            if canonical not in existing_names or (alias, canonical) in existing_pairs:
                ali_skipped += 1
                continue
            session.add(IngredientAlias(alias=alias, canonical_name=canonical, language="en"))
            existing_pairs.add((alias, canonical))
            ali_inserted += 1

        await session.commit()

    summary = {
        "ingredients_inserted": ing_inserted,
        "ingredients_skipped": ing_skipped,
        "aliases_inserted": ali_inserted,
        "aliases_skipped": ali_skipped,
    }
    log.info(
        "Backfill complete: ingredients %d inserted / %d already present; "
        "aliases %d inserted / %d already present",
        ing_inserted,
        ing_skipped,
        ali_inserted,
        ali_skipped,
    )
    return summary


if __name__ == "__main__":
    asyncio.run(backfill())
