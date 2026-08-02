"""sync expanded platform meal library

Revision ID: 050
Revises: 049
Create Date: 2026-08-02 15:00:00.000000

049 already ran on develop with the original ~10-meal seed. Expanding
``platform_meals.json`` alone does not re-run that migration, so this
revision idempotently upserts platform meals / ingredients from the current
seed JSON, and inserts any missing curated dietary ingredients + aliases
for every existing user (reference catalog gaps used by the expanded library).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from f0rge_db.rls import migration_bypass

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_RLS_TABLES = (
    "platform_meals",
    "platform_meal_ingredients",
    "dietary_ingredients",
    "ingredient_aliases",
)

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


def _data_file(filename: str) -> Path:
    override = os.environ.get("DIETARY_DATA_DIR")
    if override:
        candidate = Path(override) / filename
        if candidate.is_file():
            return candidate
    repo_path = Path(__file__).resolve().parents[2] / "data" / filename
    if repo_path.is_file():
        return repo_path
    raise FileNotFoundError(
        f"{filename} not found; set DIETARY_DATA_DIR or place file in backend/data/"
    )


def _sync_platform_meals(bind: sa.Connection) -> None:
    meals = json.loads(_data_file("platform_meals.json").read_text(encoding="utf-8"))
    for meal_data in meals:
        meal_id = bind.execute(
            sa.text(
                """
                INSERT INTO platform_meals (
                    slug, name, cuisine, icon_key, sort_order, is_active, created_at
                ) VALUES (
                    :slug, :name, :cuisine, :icon_key, :sort_order, true,
                    (now() at time zone 'utc')
                )
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    cuisine = EXCLUDED.cuisine,
                    icon_key = EXCLUDED.icon_key,
                    sort_order = EXCLUDED.sort_order,
                    is_active = true
                RETURNING id
                """
            ),
            {
                "slug": meal_data["slug"],
                "name": meal_data["name"],
                "cuisine": meal_data["cuisine"],
                "icon_key": meal_data["icon_key"],
                "sort_order": meal_data["sort_order"],
            },
        ).scalar_one()
        for index, canonical_name in enumerate(meal_data["ingredients"]):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO platform_meal_ingredients (
                        platform_meal_id, canonical_name, sort_order
                    )
                    SELECT :platform_meal_id_ins, :canonical_name_ins, :sort_order
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM platform_meal_ingredients
                        WHERE platform_meal_id = :platform_meal_id_chk
                          AND canonical_name = :canonical_name_chk
                    )
                    """
                ),
                {
                    "platform_meal_id_ins": meal_id,
                    "canonical_name_ins": canonical_name,
                    "sort_order": (index + 1) * 10,
                    "platform_meal_id_chk": meal_id,
                    "canonical_name_chk": canonical_name,
                },
            )


def _sync_curated_ingredients(bind: sa.Connection) -> None:
    payload = json.loads(_data_file("curated_ingredients_2026_07.json").read_text(encoding="utf-8"))
    source = payload.get("source", "user-research-2026-07")
    source_version = payload.get("source_version")
    user_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM users")).all()]
    if not user_ids:
        return

    for user_id in user_ids:
        for item in payload["ingredients"]:
            name = item["canonical_name"].strip().lower()
            bind.execute(
                sa.text(
                    """
                    INSERT INTO dietary_ingredients (
                        user_id, canonical_name, category, histamine_score,
                        fodmap_oligos, fodmap_fructose, fodmap_polyols, fodmap_lactose,
                        contains_gluten, contains_dairy, source, source_version,
                        archived, created_at, updated_at
                    ) VALUES (
                        :user_id, :canonical_name, :category, :histamine_score,
                        :fodmap_oligos, :fodmap_fructose, :fodmap_polyols, :fodmap_lactose,
                        :contains_gluten, :contains_dairy, :source, :source_version,
                        false, (now() at time zone 'utc'), (now() at time zone 'utc')
                    )
                    ON CONFLICT (user_id, canonical_name) DO NOTHING
                    """
                ),
                {
                    "user_id": user_id,
                    "canonical_name": name,
                    "source": source,
                    "source_version": source_version,
                    **{col: item[col] for col in _CURATED_COLS},
                },
            )
        for alias_row in payload.get("aliases", []):
            alias = (alias_row.get("alias") or alias_row.get("name") or "").strip().lower()
            canonical = (alias_row.get("canonical_name") or "").strip().lower()
            if not alias or not canonical:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO ingredient_aliases (
                        user_id, alias, canonical_name, language, created_at
                    )
                    SELECT
                        :user_id, :alias, :canonical_name, :language,
                        (now() at time zone 'utc')
                    WHERE EXISTS (
                        SELECT 1 FROM dietary_ingredients
                        WHERE user_id = :user_id_chk
                          AND canonical_name = :canonical_name_chk
                    )
                    ON CONFLICT (user_id, alias) DO NOTHING
                    """
                ),
                {
                    "user_id": user_id,
                    "alias": alias,
                    "canonical_name": canonical,
                    "language": alias_row.get("language") or "en",
                    "user_id_chk": user_id,
                    "canonical_name_chk": canonical,
                },
            )


def upgrade() -> None:
    bind = op.get_bind()
    with migration_bypass(bind, _RLS_TABLES):
        _sync_platform_meals(bind)
        _sync_curated_ingredients(bind)


def downgrade() -> None:
    # Forward-only catalog expansion; rows may already be referenced by meals.
    pass
