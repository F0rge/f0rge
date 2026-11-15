"""Preserve source product sellability without changing existing SKU behavior.

Revision ID: 086_cin7_sellability
Revises: 085_fractional_inventory
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "086_cin7_sellability"
down_revision = "085_fractional_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("is_sellable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("skus", "is_sellable")
