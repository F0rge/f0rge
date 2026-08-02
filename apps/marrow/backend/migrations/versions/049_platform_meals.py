"""platform_meals

Revision ID: 049
Revises: 048
Create Date: 2026-08-02 00:00:00.000000

Platform meal library templates (mockup A) plus nullable photo/meal filenames
for icon-only library entries.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


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


def _seed_platform_meals(bind) -> None:
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
                    ) VALUES (:platform_meal_id, :canonical_name, :sort_order)
                    """
                ),
                {
                    "platform_meal_id": meal_id,
                    "canonical_name": canonical_name,
                    "sort_order": (index + 1) * 10,
                },
            )


def upgrade() -> None:
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

    bind = op.get_bind()
    _seed_platform_meals(bind)

    op.alter_column("meals", "filename", existing_type=sa.String(), nullable=True)
    op.add_column("meals", sa.Column("icon_key", sa.String(), nullable=True))
    op.add_column("meals", sa.Column("platform_meal_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "meals_platform_meal_id_fkey",
        "meals",
        "platform_meals",
        ["platform_meal_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column("photos", "filename", existing_type=sa.String(), nullable=True)

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

    op.alter_column("photos", "filename", existing_type=sa.String(), nullable=False)
    op.drop_constraint("meals_platform_meal_id_fkey", "meals", type_="foreignkey")
    op.drop_column("meals", "platform_meal_id")
    op.drop_column("meals", "icon_key")
    op.alter_column("meals", "filename", existing_type=sa.String(), nullable=False)

    op.drop_index("ix_platform_meal_ingredients_meal_id", table_name="platform_meal_ingredients")
    op.drop_table("platform_meal_ingredients")
    op.drop_index("ix_platform_meals_cuisine", table_name="platform_meals")
    op.drop_index("ix_platform_meals_slug", table_name="platform_meals")
    op.drop_table("platform_meals")
