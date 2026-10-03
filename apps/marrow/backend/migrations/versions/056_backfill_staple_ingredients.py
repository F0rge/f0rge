"""backfill staple catalogue ingredients (muesli, flour, bread, pasta, cocoa)

Revision ID: 056
Revises: 055
Create Date: 2026-09-30 19:00:00.000000

The curated dietary catalogue had no muesli, flour, bread, pasta or cocoa, so
MCP meal logging left those staples unmatched (and therefore unflagged). The
rows live in ``data/curated_ingredients_2026_09.json`` (also read by
``scripts/load_curated.py`` for fresh seeds; new users get them through
``copy_user_catalog_from_reference``).

This revision inserts the missing rows and aliases for every existing user.
Purely additive and idempotent: ``ON CONFLICT DO NOTHING`` on
``(user_id, canonical_name)`` / ``(user_id, alias)`` means a user's own row or
alias (edited, archived, or pointing elsewhere) is never overwritten.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from f0rge_db.rls import migration_bypass

revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_RLS_TABLES = ("dietary_ingredients", "ingredient_aliases")
_DATA_FILE = "curated_ingredients_2026_09.json"

_CURATED_COLS = (
    "category",
    "histamine_score",
    "fodmap_oligos",
    "fodmap_fructose",
    "fodmap_polyols",
    "fodmap_lactose",
    "contains_gluten",
    "contains_dairy",
)

_INSERT_INGREDIENT = sa.text(
    """
    INSERT INTO dietary_ingredients (
        user_id, canonical_name, category, histamine_score,
        fodmap_oligos, fodmap_fructose, fodmap_polyols, fodmap_lactose,
        contains_gluten, contains_dairy, source, source_version,
        archived, created_at, updated_at
    )
    SELECT
        u.id, :canonical_name, :category, :histamine_score,
        :fodmap_oligos, :fodmap_fructose, :fodmap_polyols, :fodmap_lactose,
        :contains_gluten, :contains_dairy, :source, :source_version,
        false, (now() at time zone 'utc'), (now() at time zone 'utc')
    FROM users u
    ON CONFLICT (user_id, canonical_name) DO NOTHING
    """
)

# Only for users that hold the canonical (an existing user's own row is kept as-is).
_INSERT_ALIAS = sa.text(
    """
    INSERT INTO ingredient_aliases (user_id, alias, canonical_name, language, created_at)
    SELECT di.user_id, :alias, di.canonical_name, :language, (now() at time zone 'utc')
    FROM dietary_ingredients di
    WHERE di.canonical_name = :canonical_name
    ON CONFLICT (user_id, alias) DO NOTHING
    """
)


def _data_file() -> Path:
    override = os.environ.get("DIETARY_DATA_DIR")
    if override:
        candidate = Path(override) / _DATA_FILE
        if candidate.is_file():
            return candidate
    repo_path = Path(__file__).resolve().parents[2] / "data" / _DATA_FILE
    if repo_path.is_file():
        return repo_path
    raise FileNotFoundError(
        f"{_DATA_FILE} not found; set DIETARY_DATA_DIR or place file in backend/data/"
    )


def backfill_staple_ingredients(bind: sa.Connection) -> None:
    """Insert the gap-fill ingredients + aliases for all users (caller handles RLS)."""
    payload = json.loads(_data_file().read_text(encoding="utf-8"))
    source = payload["source"]
    source_version = payload.get("source_version")

    for item in payload["ingredients"]:
        bind.execute(
            _INSERT_INGREDIENT,
            {
                "canonical_name": item["canonical_name"].strip().lower(),
                "source": source,
                "source_version": source_version,
                **{col: item[col] for col in _CURATED_COLS},
            },
        )
    for alias_row in payload.get("aliases", []):
        bind.execute(
            _INSERT_ALIAS,
            {
                "alias": alias_row["alias"].strip().lower(),
                "canonical_name": alias_row["canonical_name"].strip().lower(),
                "language": alias_row.get("language") or "en",
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    with migration_bypass(bind, _RLS_TABLES):
        backfill_staple_ingredients(bind)


def downgrade() -> None:
    # Forward-only catalogue expansion; rows may already be referenced by logged meals.
    pass
