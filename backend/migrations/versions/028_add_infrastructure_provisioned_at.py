"""add_infrastructure_provisioned_at

Revision ID: 028
Revises: 027
Create Date: 2026-07-11 00:00:00.000000

Adds infrastructure_provisioned_at to users — set when diet tags and reference
catalogs are copied at signup. Replaces supplement-count idempotency check.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("infrastructure_provisioned_at", sa.DateTime(), nullable=True),
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE users SET infrastructure_provisioned_at = created_at "
            "WHERE infrastructure_provisioned_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "infrastructure_provisioned_at")
