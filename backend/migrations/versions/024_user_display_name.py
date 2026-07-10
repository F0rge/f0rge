"""user_display_name

Revision ID: 024
Revises: 023
Create Date: 2026-07-10 00:00:00.000000

Adds a nullable ``display_name`` column to ``users`` for the account
management page (#229). No backfill needed -- NULL means "no display name
set", which the API already treats as a valid response value.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
