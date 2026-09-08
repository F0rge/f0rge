"""locations table with seed rows.

Revision ID: 003_locations
Revises: 002_teams_users
Create Date: 2026-08-31

"""

from __future__ import annotations

import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_locations"
down_revision: Union[str, Sequence[str], None] = "002_teams_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOCATION_TYPES = ("warehouse", "showroom")


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        sa.CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in LOCATION_TYPES)})",
            name="ck_locations_type",
        ),
    )
    op.create_index(
        "ix_locations_name_active_lower",
        "locations",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("NOT is_archived"),
    )

    now = datetime.datetime.utcnow()
    locations = sa.table(
        "locations",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("is_archived", sa.Boolean),
        sa.column("archived_at", sa.DateTime),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        locations,
        [
            {
                "id": uuid.uuid4(),
                "name": "Kramerville",
                "type": "warehouse",
                "is_archived": False,
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Bedfordview",
                "type": "showroom",
                "is_archived": False,
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_locations_name_active_lower", table_name="locations")
    op.drop_table("locations")
