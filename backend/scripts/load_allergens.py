"""Load allergen (gluten/dairy) flags into dietary_ingredients."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "health.db"
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "allergens.json"


def load() -> None:
    log.info("Loading allergen data from %s", DATA_PATH)

    with open(DATA_PATH) as f:
        items: list[dict] = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserted = 0
    updated = 0

    for item in items:
        name = item["name"].strip().lower()
        gluten = 1 if item.get("contains_gluten", False) else 0
        dairy = 1 if item.get("contains_dairy", False) else 0

        # Check if row already exists (e.g. from SIGHI or FODMAP loads)
        cur.execute(
            "SELECT id FROM dietary_ingredients WHERE canonical_name = ?",
            (name,),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                """UPDATE dietary_ingredients
                   SET contains_gluten = ?,
                       contains_dairy = ?,
                       updated_at = datetime('now')
                 WHERE canonical_name = ?""",
                (gluten, dairy, name),
            )
            updated += 1
        else:
            cur.execute(
                """INSERT INTO dietary_ingredients
                   (canonical_name, contains_gluten, contains_dairy,
                    created_at, updated_at)
                   VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
                (name, gluten, dairy),
            )
            inserted += 1

    conn.commit()
    conn.close()

    log.info(
        "Allergen load complete: %d inserted, %d updated, %d total processed",
        inserted,
        updated,
        len(items),
    )


if __name__ == "__main__":
    load()
