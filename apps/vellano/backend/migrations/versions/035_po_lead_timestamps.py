"""PO actual lead-time stamps.

Revision ID: 035_po_lead_timestamps
Revises: 034_customer_credit
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_po_lead_timestamps"
down_revision: Union[str, Sequence[str], None] = "034_customer_credit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("on_water_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("landed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE purchase_orders SET ordered_at = created_at AT TIME ZONE 'UTC'"))


def downgrade() -> None:
    op.drop_column("purchase_orders", "received_at")
    op.drop_column("purchase_orders", "landed_at")
    op.drop_column("purchase_orders", "on_water_at")
    op.drop_column("purchase_orders", "ordered_at")
