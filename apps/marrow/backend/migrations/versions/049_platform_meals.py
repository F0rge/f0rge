"""platform_meals

Revision ID: 049
Revises: 048
Create Date: 2026-08-02 00:00:00.000000

Platform meal library templates (mockup A) plus nullable photo/meal filenames
for icon-only library entries.

Railway (and other ``--no-owner`` restores) leave ``meals`` / ``photos`` owned
by the Postgres superuser while ``MIGRATION_DATABASE_URL`` runs as ``htmigrate``.
``GRANT ALL`` does not confer DDL rights — use ``SET LOCAL ROLE`` to the table
owner (``railway_bootstrap_roles.sql`` grants the restore owner to ``htmigrate``).
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_ROLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _platform_meals_json() -> Path:
    """Resolve seed JSON in local repo layout and Docker (DIETARY_DATA_DIR)."""
    override = os.environ.get("DIETARY_DATA_DIR")
    if override:
        candidate = Path(override) / "platform_meals.json"
        if candidate.is_file():
            return candidate
    # Repo: migrations/versions/049_*.py → backend/data/
    repo_path = Path(__file__).resolve().parents[2] / "data" / "platform_meals.json"
    if repo_path.is_file():
        return repo_path
    raise FileNotFoundError(
        "platform_meals.json not found; set DIETARY_DATA_DIR or place file in backend/data/"
    )


def _table_owner(bind: sa.Connection, table: str) -> str:
    owner = bind.execute(
        sa.text(
            """
            SELECT pg_get_userbyid(c.relowner)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = :table AND n.nspname = 'public'
            """
        ),
        {"table": table},
    ).scalar_one_or_none()
    if owner is None:
        raise RuntimeError(f"table {table!r} not found in public schema")
    if not _ROLE_NAME_RE.match(owner):
        raise RuntimeError(f"unexpected table owner role name: {owner!r}")
    return owner


@contextmanager
def _as_table_owner(bind: sa.Connection, table: str) -> Generator[None, None, None]:
    """Run DDL on a pre-existing table as its owner (htmigrate is often not)."""
    owner = _table_owner(bind, table)
    bind.execute(sa.text(f"SET LOCAL ROLE {owner}"))
    try:
        yield
    finally:
        bind.execute(sa.text("RESET ROLE"))


def _has_table(bind: sa.Connection, table: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table
                """
            ),
            {"table": table},
        ).scalar_one_or_none()
    )


def _has_column(bind: sa.Connection, table: str, column: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                  AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).scalar_one_or_none()
    )


def _column_is_nullable(bind: sa.Connection, table: str, column: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"column {table}.{column} not found")
    return row == "YES"


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


def _seed_platform_meals(bind: sa.Connection) -> None:
    meals = json.loads(_platform_meals_json().read_text(encoding="utf-8"))
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
                ON CONFLICT (slug) DO NOTHING
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
        ).scalar_one_or_none()
        if meal_id is None:
            meal_id = bind.execute(
                sa.text("SELECT id FROM platform_meals WHERE slug = :slug"),
                {"slug": meal_data["slug"]},
            ).scalar_one()
        for index, canonical_name in enumerate(meal_data["ingredients"]):
            # Distinct bind names: asyncpg AmbiguousParameterError if the same
            # name appears in both the SELECT list and WHERE (AGENTS.md).
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

    if not _has_table(bind, "platform_meals"):
        op.create_table(
            "platform_meals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("cuisine", sa.String(), nullable=False),
            sa.Column("icon_key", sa.String(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
        op.create_index("ix_platform_meals_slug", "platform_meals", ["slug"], unique=True)
        op.create_index("ix_platform_meals_cuisine", "platform_meals", ["cuisine"])

    if not _has_table(bind, "platform_meal_ingredients"):
        op.create_table(
            "platform_meal_ingredients",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("platform_meal_id", sa.Integer(), nullable=False),
            sa.Column("canonical_name", sa.String(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(
                ["platform_meal_id"],
                ["platform_meals.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_platform_meal_ingredients_meal_id",
            "platform_meal_ingredients",
            ["platform_meal_id"],
        )

    _seed_platform_meals(bind)

    with _as_table_owner(bind, "meals"):
        if not _column_is_nullable(bind, "meals", "filename"):
            op.alter_column("meals", "filename", existing_type=sa.String(), nullable=True)
        if not _has_column(bind, "meals", "icon_key"):
            op.add_column("meals", sa.Column("icon_key", sa.String(), nullable=True))
        if not _has_column(bind, "meals", "platform_meal_id"):
            op.add_column(
                "meals",
                sa.Column("platform_meal_id", sa.Integer(), nullable=True),
            )
        if not bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_schema = 'public'
                  AND table_name = 'meals'
                  AND constraint_name = 'meals_platform_meal_id_fkey'
                """
            )
        ).scalar_one_or_none():
            op.create_foreign_key(
                "meals_platform_meal_id_fkey",
                "meals",
                "platform_meals",
                ["platform_meal_id"],
                ["id"],
                ondelete="SET NULL",
            )

    with _as_table_owner(bind, "photos"):
        if not _column_is_nullable(bind, "photos", "filename"):
            op.alter_column("photos", "filename", existing_type=sa.String(), nullable=True)

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
                CREATE POLICY platform_meal_ingredients_select ON platform_meal_ingredients
                    FOR SELECT
                    USING (true)
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DROP POLICY IF EXISTS platform_meal_ingredients_select ON platform_meal_ingredients"
        )
    )
    bind.execute(sa.text("ALTER TABLE platform_meal_ingredients NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE platform_meal_ingredients DISABLE ROW LEVEL SECURITY"))
    bind.execute(sa.text("DROP POLICY IF EXISTS platform_meals_select ON platform_meals"))
    bind.execute(sa.text("ALTER TABLE platform_meals NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE platform_meals DISABLE ROW LEVEL SECURITY"))

    with _as_table_owner(bind, "photos"):
        op.alter_column("photos", "filename", existing_type=sa.String(), nullable=False)

    with _as_table_owner(bind, "meals"):
        op.drop_constraint("meals_platform_meal_id_fkey", "meals", type_="foreignkey")
        op.drop_column("meals", "platform_meal_id")
        op.drop_column("meals", "icon_key")
        op.alter_column("meals", "filename", existing_type=sa.String(), nullable=False)

    op.drop_index("ix_platform_meal_ingredients_meal_id", table_name="platform_meal_ingredients")
    op.drop_table("platform_meal_ingredients")
    op.drop_index("ix_platform_meals_cuisine", table_name="platform_meals")
    op.drop_index("ix_platform_meals_slug", table_name="platform_meals")
    op.drop_table("platform_meals")
