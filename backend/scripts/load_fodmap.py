"""Load FODMAP data into dietary_ingredients."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "health.db"
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "fodmap_list.json"


def load() -> None:
    log.info("Loading FODMAP data from %s", DATA_PATH)

    with open(DATA_PATH) as f:
        items: list[dict] = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserted = 0
    updated = 0

    for item in items:
        name = item["name"].strip().lower()
        oligos = item.get("oligos", "low")
        fructose = item.get("fructose", "low")
        polyols = item.get("polyols", "low")
        lactose = item.get("lactose", "low")

        # Check if row already exists (e.g. from SIGHI load)
        cur.execute(
            "SELECT id FROM dietary_ingredients WHERE canonical_name = ?",
            (name,),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                """UPDATE dietary_ingredients
                   SET fodmap_oligos = ?,
                       fodmap_fructose = ?,
                       fodmap_polyols = ?,
                       fodmap_lactose = ?,
                       updated_at = datetime('now')
                 WHERE canonical_name = ?""",
                (oligos, fructose, polyols, lactose, name),
            )
            updated += 1
        else:
            cur.execute(
                """INSERT INTO dietary_ingredients
                   (canonical_name, fodmap_oligos, fodmap_fructose, fodmap_polyols,
                    fodmap_lactose, contains_gluten, contains_dairy,
                    source, source_version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 0, 0, 'monash', '2024',
                           datetime('now'), datetime('now'))""",
                (name, oligos, fructose, polyols, lactose),
            )
            inserted += 1

    conn.commit()
    conn.close()

    log.info(
        "FODMAP load complete: %d inserted, %d updated, %d total processed",
        inserted,
        updated,
        len(items),
    )


if __name__ == "__main__":
    load()
