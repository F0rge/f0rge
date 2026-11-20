"""Give held sales an expiry; existing ones get three hours from the migration.

Revision ID: 100_held_sale_expiry
Revises: 099_stock_reservations
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "100_held_sale_expiry"
down_revision = "099_stock_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("held_sales", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE held_sales SET expires_at = now() + interval '3 hours'")
    op.alter_column("held_sales", "expires_at", nullable=False)


def downgrade() -> None:
    op.drop_column("held_sales", "expires_at")
