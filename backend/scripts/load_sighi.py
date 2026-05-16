"""Load SIGHI histamine compatibility data into dietary_ingredients."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from scripts._paths import data_dir

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "health.db"
DATA_PATH = data_dir() / "sighi_histamine.json"


def load() -> None:
    log.info("Loading SIGHI histamine data from %s", DATA_PATH)

    with open(DATA_PATH) as f:
        items: list[dict] = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserted = 0
    updated = 0

    for item in items:
        name = item["name"].strip().lower()
        category = item.get("category", "").strip().lower() or None
        score = item["score"]

        # Check if row already exists
        cur.execute(
            "SELECT id FROM dietary_ingredients WHERE canonical_name = ?",
            (name,),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                """UPDATE dietary_ingredients
                   SET category = COALESCE(?, category),
                       histamine_score = ?,
                       source = 'sighi',
                       source_version = '2024',
                       updated_at = datetime('now')
                 WHERE canonical_name = ?""",
                (category, score, name),
            )
            updated += 1
        else:
            cur.execute(
                """INSERT INTO dietary_ingredients
                   (canonical_name, category, histamine_score, source, source_version,
                    contains_gluten, contains_dairy, created_at, updated_at)
                   VALUES (?, ?, ?, 'sighi', '2024', 0, 0, datetime('now'), datetime('now'))""",
                (name, category, score),
            )
            inserted += 1

    conn.commit()
    conn.close()

    log.info(
        "SIGHI load complete: %d inserted, %d updated, %d total processed",
        inserted,
        updated,
        len(items),
    )


if __name__ == "__main__":
    load()
