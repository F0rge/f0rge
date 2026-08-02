"""grant platform meal library to app roles

Revision ID: 051
Revises: 050
Create Date: 2026-08-02 15:50:00.000000

``049`` / ``050`` create ``platform_meals`` as the migrator role. Default
privileges set in ``019`` / bootstrap apply to the role that ran those
statements, not necessarily ``htmigrate``, so ``healthtracker_app`` can lack
SELECT on the new tables — ``GET /meals/library`` then 500s while user-owned
tables still work.

Grant table + sequence privileges, ensure SELECT RLS policies exist, and
re-sync the seed JSON so develop picks up the expanded catalog if ``050``
did not apply cleanly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from f0rge_db.rls import migration_bypass

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_PLATFORM_TABLES = ("platform_meals", "platform_meal_ingredients")
_APP_ROLES = ("healthtracker_app", "healthtracker_ro", "htmigrate")


def _role_exists(bind: sa.Connection, role: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar_one_or_none()
    )


def _has_policy(bind: sa.Connection, table: str, policy: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = :table
                  AND policyname = :policy
                """
            ),
            {"table": table, "policy": policy},
        ).scalar_one_or_none()
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


def _grant_platform_tables(bind: sa.Connection) -> None:
    if _role_exists(bind, "healthtracker_app"):
        bind.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON platform_meals, "
                "platform_meal_ingredients TO healthtracker_app"
            )
        )
        bind.execute(
            sa.text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO healthtracker_app")
        )
    if _role_exists(bind, "healthtracker_ro"):
        bind.execute(
            sa.text("GRANT SELECT ON platform_meals, platform_meal_ingredients TO healthtracker_ro")
        )
    if _role_exists(bind, "htmigrate"):
        # Future objects created by the migrator inherit app/ro grants.
        bind.execute(
            sa.text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE htmigrate IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO healthtracker_app"
            )
        )
        bind.execute(
            sa.text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE htmigrate IN SCHEMA public "
                "GRANT SELECT ON TABLES TO healthtracker_ro"
            )
        )
        bind.execute(
            sa.text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE htmigrate IN SCHEMA public "
                "GRANT USAGE, SELECT ON SEQUENCES TO healthtracker_app, htmigrate"
            )
        )


def _ensure_select_policies(bind: sa.Connection) -> None:
    if not _has_policy(bind, "platform_meals", "platform_meals_select"):
        bind.execute(sa.text("ALTER TABLE platform_meals ENABLE ROW LEVEL SECURITY"))
        bind.execute(sa.text("ALTER TABLE platform_meals FORCE ROW LEVEL SECURITY"))
        bind.execute(
            sa.text(
                """
                CREATE POLICY platform_meals_select ON platform_meals
                    FOR SELECT
                    USING (true)
                """
            )
        )
    if not _has_policy(bind, "platform_meal_ingredients", "platform_meal_ingredients_select"):
        bind.execute(sa.text("ALTER TABLE platform_meal_ingredients ENABLE ROW LEVEL SECURITY"))
        bind.execute(sa.text("ALTER TABLE platform_meal_ingredients FORCE ROW LEVEL SECURITY"))
        bind.execute(
            sa.text(
                """
                CREATE POLICY platform_meal_ingredients_select
                    ON platform_meal_ingredients
                    FOR SELECT
                    USING (true)
                """
            )
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


def upgrade() -> None:
    bind = op.get_bind()
    _grant_platform_tables(bind)
    _ensure_select_policies(bind)
    with migration_bypass(bind, _PLATFORM_TABLES):
        _sync_platform_meals(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if _role_exists(bind, "healthtracker_app"):
        bind.execute(
            sa.text(
                "REVOKE ALL PRIVILEGES ON platform_meals, "
                "platform_meal_ingredients FROM healthtracker_app"
            )
        )
    if _role_exists(bind, "healthtracker_ro"):
        bind.execute(
            sa.text(
                "REVOKE ALL PRIVILEGES ON platform_meals, "
                "platform_meal_ingredients FROM healthtracker_ro"
            )
        )
