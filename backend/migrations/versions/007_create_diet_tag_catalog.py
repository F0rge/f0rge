"""create_diet_tag_catalog

Revision ID: 007
Revises: a1b2c3d4e506
Create Date: 2026-05-25 00:00:00.000000

Creates the diet_tag_catalog table — a DB-backed replacement for the
hardcoded DIET_OPTIONS constant in food-card.tsx.  The 4 seed rows use
the exact same keys as the existing constants so that historical
entry.diet_risk CSV values (e.g. "high-histamine,gluten") continue to
resolve correctly via the new catalog lookup.

Keys are inserted verbatim with hyphens — do NOT normalise them to
underscores; historical entry rows depend on the hyphenated form.

Down-migration drops the index then the table.  No seed-undo is needed
because the table itself is removed.
"""

from __future__ import annotations

import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "a1b2c3d4e506"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "diet_tag_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("first_used_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_diet_tag_catalog_key"), "diet_tag_catalog", ["key"], unique=True
    )

    # Seed 4 default rows.
    # Using op.bulk_insert with a lightweight sa.Table definition — the canonical
    # pattern for seeding in migrations.  We deliberately do NOT import the
    # SQLAlchemy model; models can drift, migrations must be frozen-in-time.
    now = datetime.datetime.utcnow()
    diet_tag_catalog = sa.table(
        "diet_tag_catalog",
        sa.column("key", sa.String()),
        sa.column("label", sa.String()),
        sa.column("archived", sa.Boolean()),
        sa.column("first_used_at", sa.DateTime()),
        sa.column("last_used_at", sa.DateTime()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        diet_tag_catalog,
        [
            {
                "key": "high-histamine",
                "label": "High-histamine",
                "archived": False,
                "first_used_at": None,
                "last_used_at": None,
                "sort_order": 0,
                "created_at": now,
                "updated_at": now,
            },
            {
                "key": "high-fodmap",
                "label": "High-FODMAP",
                "archived": False,
                "first_used_at": None,
                "last_used_at": None,
                "sort_order": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "key": "gluten",
                "label": "Gluten",
                "archived": False,
                "first_used_at": None,
                "last_used_at": None,
                "sort_order": 2,
                "created_at": now,
                "updated_at": now,
            },
            {
                "key": "dairy",
                "label": "Dairy",
                "archived": False,
                "first_used_at": None,
                "last_used_at": None,
                "sort_order": 3,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_diet_tag_catalog_key"), table_name="diet_tag_catalog")
    op.drop_table("diet_tag_catalog")
