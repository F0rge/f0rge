"""add_user_avatar

Revision ID: 026
Revises: 025
Create Date: 2026-07-10 00:00:00.000000

Adds avatar_default_index (0-31) and optional avatar_custom_filename to users.
Backfills existing users with a stable hash-based default index.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_default_index", sa.SmallInteger(), nullable=True))
    op.add_column("users", sa.Column("avatar_custom_filename", sa.String(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE users SET avatar_default_index = "
            "(get_byte(decode(replace(id::text, '-', ''), 'hex'), 15) % 32)"
        )
    )
    op.alter_column("users", "avatar_default_index", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "avatar_custom_filename")
    op.drop_column("users", "avatar_default_index")
