"""symptom events json

Revision ID: 054
Revises: 053
Create Date: 2026-08-31 16:20:00.000000

Timed symptom stamps on the daily log. ``symptoms_json`` stays the day's
current score; ``symptom_events_json`` is the clock (same shape as
``medications_json``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMN = "symptom_events_json"
_TABLE = "entries"


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


def upgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, _TABLE, _COLUMN):
        return
    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, _TABLE, _COLUMN):
        return
    op.drop_column(_TABLE, _COLUMN)
