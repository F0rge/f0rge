"""Add the company sale hold time to team settings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "097_till_hold_hours"
down_revision = "096_mcp_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column("till_hold_hours", sa.Integer(), nullable=False, server_default=sa.text("3")),
    )
    op.create_check_constraint(
        "ck_team_settings_till_hold_hours",
        "team_settings",
        "till_hold_hours >= 1 AND till_hold_hours <= 24",
    )


def downgrade() -> None:
    op.drop_constraint("ck_team_settings_till_hold_hours", "team_settings", type_="check")
    op.drop_column("team_settings", "till_hold_hours")
