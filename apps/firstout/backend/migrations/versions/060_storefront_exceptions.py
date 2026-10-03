"""Operator commerce exception queue, audits, and test alerts.

Revision ID: 060_storefront_exceptions
Revises: 059_storefront_refunds
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "060_storefront_exceptions"
down_revision: Union[str, Sequence[str], None] = "059_storefront_refunds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "storefront_commerce_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("seed_key", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("explanation", sa.String(length=500), nullable=False),
        sa.Column("safe_action", sa.String(length=64), nullable=False),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=True),
        sa.Column("payment_reference", sa.String(length=128), nullable=True),
        sa.Column("customer_email", sa.String(length=254), nullable=True),
        sa.Column("provider_verified", sa.Boolean(), nullable=False),
        sa.Column("blocks_checkout", sa.Boolean(), nullable=False),
        sa.Column("effect_applied", sa.Boolean(), nullable=False),
        sa.Column("repair_count", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('aged_hold', 'stale_sync', 'missing_operational_paid_order', "
            "'unknown_payment', 'refund_mismatch', 'fulfilment_drift', 'capacity_conflict')",
            name="ck_storefront_exceptions_kind",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'aged', 'terminal', 'resolved')",
            name="ck_storefront_exceptions_status",
        ),
        sa.CheckConstraint("repair_count >= 0", name="ck_storefront_exceptions_repair_count"),
        sa.CheckConstraint(
            "amount_minor IS NULL OR amount_minor > 0",
            name="ck_storefront_exceptions_amount",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "seed_key", name="uq_storefront_exception_seed"),
    )
    op.create_index(
        "ix_storefront_commerce_exceptions_company_id",
        "storefront_commerce_exceptions",
        ["company_id"],
    )
    op.create_table(
        "storefront_exception_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("exception_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('repaired', 'already_resolved', 'denied', 'needs_provider')",
            name="ck_storefront_exception_audit_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["exception_id"],
            ["storefront_commerce_exceptions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exception_id", "idempotency_key", name="uq_storefront_exception_audit_key"
        ),
    )
    op.create_table(
        "storefront_exception_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exception_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("queue_class", sa.String(length=16), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "queue_class IN ('aged', 'terminal', 'retrying')",
            name="ck_storefront_exception_alert_class",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["exception_id"],
            ["storefront_commerce_exceptions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("storefront_exception_alerts")
    op.drop_table("storefront_exception_audits")
    op.drop_index(
        "ix_storefront_commerce_exceptions_company_id",
        table_name="storefront_commerce_exceptions",
    )
    op.drop_table("storefront_commerce_exceptions")
