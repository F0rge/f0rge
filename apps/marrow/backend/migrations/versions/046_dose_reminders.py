"""dose_reminders

Revision ID: 045
Revises: 044
Create Date: 2026-07-18 00:00:00.000000

Dose reminder scheduler substrate (#390): per-user timezone, optional
per-treatment reminder time overrides, and a notification dedupe key whose
partial unique index doubles as the multi-instance lock (ON CONFLICT DO
NOTHING) for the reminder loop.

ponytail: no API endpoint to set user_settings.timezone — both users are
Europe/Luxembourg, the server_default covers them. Add an endpoint when a
user outside that timezone shows up.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "timezone",
            sa.String(),
            nullable=False,
            server_default="Europe/Luxembourg",
        ),
    )
    op.add_column(
        "treatments",
        sa.Column("reminder_times", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("dedupe_key", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_notifications_dedupe_key",
        "notifications",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notifications_dedupe_key",
        table_name="notifications",
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    op.drop_column("notifications", "dedupe_key")
    op.drop_column("treatments", "reminder_times")
    op.drop_column("user_settings", "timezone")
