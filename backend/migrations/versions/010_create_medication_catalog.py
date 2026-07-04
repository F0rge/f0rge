"""create_medication_catalog

Revision ID: 010
Revises: 009
Create Date: 2026-07-04 00:00:00.000000

Adds a Medications feature: a `medication_catalog` table (mirrors
`supplement_catalog`/`diet_tag_catalog` field-for-field) plus a
`medications_json` column on `entries` holding a JSON list of per-day
medication-intake events, e.g.::

    [{"key": "ibuprofen", "dose": "400mg", "reason": "headache", "time": "15:20"}]

Unlike `supplement_catalog`, Ibuprofen was previously hand-added to
`supplement_catalog` by the user -- that row is left untouched here (it
nags as an unticked daily chip until the user archives it themselves in
the UI). This migration only adds the new table/column/seed rows.

`key` on a medications_json entry is NOT FK-constrained against
medication_catalog -- same leniency as supplements/diet tags, so a
historical entry keeps its logged key even after the catalog item is
archived.

Seed rows use the sa.table()+op.bulk_insert() pattern (no ORM model
import -- migrations must be frozen-in-time). Down-migration drops the
column and the table; no seed-undo needed because the table itself is
removed.
"""

from __future__ import annotations

import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.seed_data import DEFAULT_MEDICATIONS

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medication_catalog",
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
    op.create_index(op.f("ix_medication_catalog_key"), "medication_catalog", ["key"], unique=True)

    op.add_column(
        "entries",
        sa.Column(
            "medications_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )

    now = datetime.datetime.utcnow()
    medication_catalog = sa.table(
        "medication_catalog",
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
        medication_catalog,
        [
            {
                "key": key,
                "label": label,
                "archived": False,
                "first_used_at": None,
                "last_used_at": None,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            }
            for sort_order, (key, label) in enumerate(DEFAULT_MEDICATIONS)
        ],
    )


def downgrade() -> None:
    op.drop_column("entries", "medications_json")
    op.drop_index(op.f("ix_medication_catalog_key"), table_name="medication_catalog")
    op.drop_table("medication_catalog")
