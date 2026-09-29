"""Persist immutable fulfilment promises and durable Storefront status messages.

Revision ID: 058_storefront_fulfillment
Revises: 057_made_to_order_offers
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "058_storefront_fulfillment"
down_revision: Union[str, Sequence[str], None] = "057_made_to_order_offers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_orders",
        sa.Column("fulfillment_promise", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "sales_order_lines",
        sa.Column("fulfillment_promise", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "ops_commerce_orders",
        sa.Column(
            "fulfillment_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'confirmed'"),
        ),
    )
    op.add_column(
        "ops_commerce_orders",
        sa.Column(
            "fulfillment_revision", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.create_check_constraint(
        "ck_ops_commerce_orders_fulfillment_status",
        "ops_commerce_orders",
        "fulfillment_status IN ('confirmed', 'ready_for_delivery', 'out_for_delivery', "
        "'delivered', 'ready_for_collection', 'collected')",
    )
    op.create_check_constraint(
        "ck_ops_commerce_orders_fulfillment_revision",
        "ops_commerce_orders",
        "fulfillment_revision >= 0",
    )
    op.create_table(
        "ops_commerce_fulfillment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handoff_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_order_id", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("fulfillment_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("fulfillment_promise", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("revision > 0", name="ck_ops_commerce_fulfillment_events_revision"),
        sa.CheckConstraint(
            "fulfillment_type IN ('delivery', 'collection')",
            name="ck_ops_commerce_fulfillment_events_type",
        ),
        sa.CheckConstraint(
            "status IN ('ready_for_delivery', 'out_for_delivery', 'delivered', "
            "'ready_for_collection', 'collected')",
            name="ck_ops_commerce_fulfillment_events_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["handoff_id"], ["ops_commerce_orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "handoff_id", "revision", name="uq_ops_commerce_fulfillment_event_revision"
        ),
    )
    op.create_index(
        "ix_ops_commerce_fulfillment_events_pending",
        "ops_commerce_fulfillment_events",
        ["company_id", "occurred_at"],
        unique=False,
        postgresql_where=sa.text("acknowledged_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ops_commerce_fulfillment_events_pending",
        table_name="ops_commerce_fulfillment_events",
    )
    op.drop_table("ops_commerce_fulfillment_events")
    op.drop_constraint(
        "ck_ops_commerce_orders_fulfillment_revision", "ops_commerce_orders", type_="check"
    )
    op.drop_constraint(
        "ck_ops_commerce_orders_fulfillment_status", "ops_commerce_orders", type_="check"
    )
    op.drop_column("ops_commerce_orders", "fulfillment_revision")
    op.drop_column("ops_commerce_orders", "fulfillment_status")
    op.drop_column("sales_order_lines", "fulfillment_promise")
    op.drop_column("sales_orders", "fulfillment_promise")
