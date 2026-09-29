"""Add finite, expiring made-to-order offers to Firstout SKUs.

Revision ID: 057_made_to_order_offers
Revises: 056_storefront_order_handoffs
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "057_made_to_order_offers"
down_revision: Union[str, Sequence[str], None] = "056_storefront_order_handoffs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("made_to_order_capacity", sa.Integer(), nullable=True))
    op.add_column(
        "skus",
        sa.Column("made_to_order_lead_time_min_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "skus",
        sa.Column("made_to_order_lead_time_max_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "skus",
        sa.Column("made_to_order_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "skus",
        sa.Column("made_to_order_offer_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_skus_made_to_order_offer_id", "skus", ["made_to_order_offer_id"]
    )
    op.create_check_constraint(
        "ck_skus_made_to_order_offer_complete",
        "skus",
        "(made_to_order_capacity IS NULL AND made_to_order_lead_time_min_days IS NULL "
        "AND made_to_order_lead_time_max_days IS NULL AND made_to_order_expires_at IS NULL "
        "AND made_to_order_offer_id IS NULL) OR "
        "(made_to_order_capacity >= 0 AND made_to_order_lead_time_min_days >= 1 "
        "AND made_to_order_lead_time_max_days >= made_to_order_lead_time_min_days "
        "AND made_to_order_expires_at IS NOT NULL AND made_to_order_offer_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_skus_made_to_order_offer_complete", "skus", type_="check")
    op.drop_constraint("uq_skus_made_to_order_offer_id", "skus", type_="unique")
    op.drop_column("skus", "made_to_order_offer_id")
    op.drop_column("skus", "made_to_order_expires_at")
    op.drop_column("skus", "made_to_order_lead_time_max_days")
    op.drop_column("skus", "made_to_order_lead_time_min_days")
    op.drop_column("skus", "made_to_order_capacity")
