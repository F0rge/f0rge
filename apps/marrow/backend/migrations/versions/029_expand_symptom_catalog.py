"""expand_symptom_catalog

Revision ID: 029
Revises: 028
Create Date: 2026-07-11 12:00:00.000000

Bulk-seeds ~120 symptom reference rows for the reference user (Leo) so they are
discoverable via onboarding / customize search without flooding the daily picker.
Rows are inserted archived=true — same rationale as migration 011 for supplements.

Row data lives in app/seed_data.py (BULK_SYMPTOMS) — imported as plain data, no
ORM model import, per the migration-seed convention.

Idempotent via ON CONFLICT (user_id, key) DO NOTHING.
"""

from __future__ import annotations

import datetime
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.seed_data import BULK_SYMPTOMS, DEFAULT_SYMPTOMS

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _reference_user_id() -> str:
    return os.environ.get("DEFAULT_STORAGE_USER_ID", "00000000-0000-0000-0000-000000000001")


def _symptom_catalog_table() -> sa.Table:
    return sa.table(
        "symptom_catalog",
        sa.column("user_id", postgresql.UUID(as_uuid=False)),
        sa.column("key", sa.String()),
        sa.column("label", sa.String()),
        sa.column("archived", sa.Boolean()),
        sa.column("first_used_at", sa.DateTime()),
        sa.column("last_used_at", sa.DateTime()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )


def upgrade() -> None:
    now = datetime.datetime.utcnow()
    user_id = _reference_user_id()
    # DEFAULT_SYMPTOMS (migration 009) has 7 entries, positions 0-6.
    start_sort_order = len(DEFAULT_SYMPTOMS)
    rows = [
        {
            "user_id": user_id,
            "key": key,
            "label": label,
            "archived": True,
            "first_used_at": None,
            "last_used_at": None,
            "sort_order": start_sort_order + i,
            "created_at": now,
            "updated_at": now,
        }
        for i, (key, label) in enumerate(BULK_SYMPTOMS)
    ]
    if not rows:
        return
    bind = op.get_bind()
    # Fly MPG runs alembic with FORCE RLS — tenant policies block inserts unless
    # app.user_id matches the reference user we're seeding for.
    bind.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": user_id},
    )
    table = _symptom_catalog_table()
    stmt = (
        postgresql.insert(table)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_symptom_catalog_user_id_key")
    )
    op.execute(stmt)


def downgrade() -> None:
    bulk_keys = [key for key, _ in BULK_SYMPTOMS]
    user_id = _reference_user_id()
    bind = op.get_bind()
    bind.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": user_id},
    )
    op.execute(
        sa.text(
            "DELETE FROM symptom_catalog WHERE user_id = :user_id AND key = ANY(:keys)"
        ).bindparams(
            sa.bindparam("user_id", value=user_id),
            sa.bindparam("keys", value=bulk_keys, type_=postgresql.ARRAY(sa.String())),
        )
    )
