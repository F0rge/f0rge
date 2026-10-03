"""Durable Storefront refund commands and signed provider observations.

Revision ID: 059_storefront_refunds
Revises: 058_storefront_fulfillment
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "059_storefront_refunds"
down_revision: Union[str, Sequence[str], None] = "058_storefront_fulfillment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ops_commerce_orders", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.drop_constraint(
        "ck_ops_commerce_orders_fulfillment_status", "ops_commerce_orders", type_="check"
    )
    op.create_check_constraint(
        "ck_ops_commerce_orders_fulfillment_status",
        "ops_commerce_orders",
        "fulfillment_status IN ('confirmed', 'ready_for_delivery', 'out_for_delivery', "
        "'delivered', 'ready_for_collection', 'collected', 'cancelled')",
    )
    op.drop_constraint(
        "ck_ops_commerce_fulfillment_events_status",
        "ops_commerce_fulfillment_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ops_commerce_fulfillment_events_status",
        "ops_commerce_fulfillment_events",
        "status IN ('ready_for_delivery', 'out_for_delivery', 'delivered', "
        "'ready_for_collection', 'collected', 'cancelled')",
    )
    op.create_table(
        "ops_commerce_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handoff_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_origin", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("provider_amount_minor", sa.Integer(), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("allocation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("selected_lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cancel_order", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_outcome", sa.String(length=16), nullable=True),
        sa.Column("provider_refund_id", sa.String(length=128), nullable=True),
        sa.Column("provider_result_code", sa.String(length=32), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("sales_order_balance_adjusted", sa.Boolean(), nullable=False),
        sa.Column("financial_journal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("amount_minor > 0", name="ck_ops_commerce_refunds_amount"),
        sa.CheckConstraint(
            "provider_amount_minor IS NULL OR provider_amount_minor > 0",
            name="ck_ops_commerce_refunds_provider_amount",
        ),
        sa.CheckConstraint("currency_code = 'ZAR'", name="ck_ops_commerce_refunds_currency"),
        sa.CheckConstraint(
            "request_origin IN ('staff', 'provider')", name="ck_ops_commerce_refunds_origin"
        ),
        sa.CheckConstraint(
            "status IN ('requested', 'dispatching', 'unknown', 'pending', 'succeeded', 'failed', 'needs_review')",
            name="ck_ops_commerce_refunds_status",
        ),
        sa.CheckConstraint(
            "provider_outcome IS NULL OR provider_outcome IN ('succeeded', 'pending', 'failed', 'unknown')",
            name="ck_ops_commerce_refunds_provider_outcome",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["handoff_id"], ["ops_commerce_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["financial_journal_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handoff_id", "idempotency_key", name="uq_ops_commerce_refund_key"),
        sa.UniqueConstraint("provider_refund_id", name="uq_ops_commerce_refund_provider_id"),
    )
    op.create_index(
        "ix_ops_commerce_refunds_open",
        "ops_commerce_refunds",
        ["handoff_id", "created_at"],
        postgresql_where=sa.text("status IN ('requested', 'dispatching', 'unknown', 'pending')"),
    )
    op.create_table(
        "ops_commerce_refund_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handoff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("refund_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_refund_id", sa.String(length=128), nullable=False),
        sa.Column("event_key", sa.String(length=260), nullable=False),
        sa.Column("webhook_id", sa.String(length=200), nullable=True),
        sa.Column("referenced_capture_id", sa.String(length=128), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("result_code", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("canonical_sha256", sa.String(length=64), nullable=False),
        sa.Column("resolution_code", sa.String(length=64), nullable=True),
        sa.Column("provider_event_at", sa.DateTime(), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("financial_journal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_minor > 0", name="ck_ops_commerce_refund_events_amount"),
        sa.CheckConstraint("currency_code = 'ZAR'", name="ck_ops_commerce_refund_events_currency"),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'pending', 'failed', 'unknown', 'needs_review')",
            name="ck_ops_commerce_refund_events_outcome",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["handoff_id"], ["ops_commerce_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["refund_id"], ["ops_commerce_refunds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["financial_journal_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_ops_commerce_refund_events_event_key"),
        sa.UniqueConstraint("webhook_id", name="uq_ops_commerce_refund_events_webhook_id"),
    )
    op.execute(
        "INSERT INTO role_permissions (role_id, key) "
        "SELECT id, 'sales.refunds' FROM roles WHERE slug IN ('owner', 'books') "
        "ON CONFLICT (role_id, key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE key = 'sales.refunds'")
    op.drop_table("ops_commerce_refund_events")
    op.drop_index("ix_ops_commerce_refunds_open", table_name="ops_commerce_refunds")
    op.drop_table("ops_commerce_refunds")
    op.drop_constraint(
        "ck_ops_commerce_fulfillment_events_status",
        "ops_commerce_fulfillment_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ops_commerce_fulfillment_events_status",
        "ops_commerce_fulfillment_events",
        "status IN ('ready_for_delivery', 'out_for_delivery', 'delivered', "
        "'ready_for_collection', 'collected')",
    )
    op.drop_constraint(
        "ck_ops_commerce_orders_fulfillment_status", "ops_commerce_orders", type_="check"
    )
    op.create_check_constraint(
        "ck_ops_commerce_orders_fulfillment_status",
        "ops_commerce_orders",
        "fulfillment_status IN ('confirmed', 'ready_for_delivery', 'out_for_delivery', "
        "'delivered', 'ready_for_collection', 'collected')",
    )
    op.drop_column("ops_commerce_orders", "cancelled_at")
