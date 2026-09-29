"""Persist Storefront paid orders, external tender, and reconciliation state.

Revision ID: 056_storefront_order_handoffs
Revises: 055_ops_commerce_acks
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "056_storefront_order_handoffs"
down_revision: Union[str, Sequence[str], None] = "055_ops_commerce_acks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
STOREFRONT_CLEARING_ACCOUNT_ID = "7bb8c6f1-70f8-49c2-a2d3-a68dc496b4e1"


def upgrade() -> None:
    op.create_table(
        "ops_commerce_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("external_order_id", sa.String(length=255), nullable=False),
        sa.Column("external_payment_id", sa.String(length=255), nullable=False),
        sa.Column("gateway_provider", sa.String(length=64), nullable=False),
        sa.Column("gateway_reference", sa.String(length=255), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("captured_amount_minor", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_journal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'stock_conflict', 'imported', 'failed')",
            name="ck_ops_commerce_orders_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ops_commerce_orders_attempt_count"),
        sa.CheckConstraint(
            "captured_amount_minor > 0", name="ck_ops_commerce_orders_captured_amount"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_journal_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "channel", "external_order_id", name="uq_ops_commerce_order_identity"
        ),
        sa.UniqueConstraint(
            "company_id", "channel", "external_payment_id", name="uq_ops_commerce_payment_identity"
        ),
    )
    op.create_index("ix_ops_commerce_orders_created_at", "ops_commerce_orders", ["created_at"])

    # A non-bank asset keeps the provider's unsettled balance distinct from cash/EFT.
    op.execute(
        sa.text(
            "INSERT INTO accounts (id, code, name, type, is_system, is_archived, is_bank, "
            "tax_treatment, created_at, updated_at) "
            f"VALUES ('{STOREFRONT_CLEARING_ACCOUNT_ID}', '1150', 'Storefront gateway clearing', 'asset', true, "
            "false, false, 'none', now(), now()) ON CONFLICT (code) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM accounts WHERE code = '1150' "
            "AND name = 'Storefront gateway clearing' AND type = 'asset' AND is_system = true "
            "AND is_archived = false AND is_bank = false) THEN "
            "RAISE EXCEPTION 'Account code 1150 is already assigned to an incompatible account'; "
            "END IF; END $$"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_ops_commerce_orders_created_at", table_name="ops_commerce_orders")
    op.drop_table("ops_commerce_orders")
    op.execute(
        sa.text(
            f"DELETE FROM accounts WHERE id = '{STOREFRONT_CLEARING_ACCOUNT_ID}' "
            "AND code = '1150' AND NOT EXISTS (SELECT 1 FROM journal_lines "
            f"WHERE journal_lines.account_id = '{STOREFRONT_CLEARING_ACCOUNT_ID}') "
            "AND NOT EXISTS (SELECT 1 FROM bank_rules "
            f"WHERE bank_account_id = '{STOREFRONT_CLEARING_ACCOUNT_ID}' "
            f"OR target_account_id = '{STOREFRONT_CLEARING_ACCOUNT_ID}') "
            "AND NOT EXISTS (SELECT 1 FROM bank_imports "
            f"WHERE account_id = '{STOREFRONT_CLEARING_ACCOUNT_ID}')"
        )
    )
