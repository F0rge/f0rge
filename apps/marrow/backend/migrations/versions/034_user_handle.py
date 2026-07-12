"""user_handle

Revision ID: 034
Revises: 033
Create Date: 2026-07-12 00:00:00.000000

Adds nullable unique ``handle`` column to ``users`` for the Marrow social layer (#303).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("handle", postgresql.CITEXT(), nullable=True))
    op.create_unique_constraint("uq_users_handle", "users", ["handle"])
    op.create_check_constraint(
        "ck_users_handle_format",
        "users",
        "handle ~ '^[a-z0-9_]{3,30}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_handle_format", "users", type_="check")
    op.drop_constraint("uq_users_handle", "users", type_="unique")
    op.drop_column("users", "handle")
