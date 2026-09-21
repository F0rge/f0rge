"""Nia monthly token caps on team settings and users.

Revision ID: 039_nia_caps
Revises: 038_nia_hitl
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039_nia_caps"
down_revision: Union[str, Sequence[str], None] = "038_nia_hitl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column(
            "nia_monthly_token_cap",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("500000"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("nia_monthly_token_cap", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "nia_monthly_token_cap")
    op.drop_column("team_settings", "nia_monthly_token_cap")
