"""backfill_and_notnull_timestamps

Revision ID: 023
Revises: 022
Create Date: 2026-07-10 00:00:00.000000

Fixes model<->DB NOT NULL drift on three timestamp columns that the ORM
declares as ``Mapped[datetime.datetime]`` (non-nullable) but the DB has
always allowed NULL: ``embedding.created_at``, ``user_settings.created_at``,
``user_settings.updated_at``. All three are populated via ``default=utcnow``
in practice, so a NULL backfill followed by SET NOT NULL is safe.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("embedding", "created_at"),
    ("user_settings", "created_at"),
    ("user_settings", "updated_at"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in _COLUMNS:
        bind.execute(sa.text(f"UPDATE {table} SET {column} = now() WHERE {column} IS NULL"))
        op.alter_column(table, column, nullable=False)


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=True)
