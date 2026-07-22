"""checkin_defaults

Revision ID: 048
Revises: 047
Create Date: 2026-07-22 00:00:00.000000

Per-user daily check-in defaults for supplements and symptoms on user_settings.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("default_supplements", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "default_symptoms_json",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "default_symptoms_json")
    op.drop_column("user_settings", "default_supplements")
