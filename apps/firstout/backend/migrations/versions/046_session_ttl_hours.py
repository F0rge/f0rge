"""Team session TTL hours on team_settings.

Revision ID: 046_session_ttl_hours
Revises: 045_po_approval_statuses
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046_session_ttl_hours"
down_revision: Union[str, Sequence[str], None] = "045_po_approval_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column("session_ttl_hours", sa.Integer(), nullable=False, server_default="12"),
    )
    op.create_check_constraint(
        "ck_team_settings_session_ttl_hours",
        "team_settings",
        "session_ttl_hours >= 1 AND session_ttl_hours <= 720",
    )


def downgrade() -> None:
    op.drop_constraint("ck_team_settings_session_ttl_hours", "team_settings", type_="check")
    op.drop_column("team_settings", "session_ttl_hours")
