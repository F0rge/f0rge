"""add_onboarding_completed_at

Revision ID: 027
Revises: 026
Create Date: 2026-07-10 00:00:00.000000

Adds onboarding_completed_at to user_settings. Backfills existing rows so
current users are not forced through the onboarding tour.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text("UPDATE user_settings SET onboarding_completed_at = NOW() WHERE onboarding_completed_at IS NULL")
    )


def downgrade() -> None:
    op.drop_column("user_settings", "onboarding_completed_at")
