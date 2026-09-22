"""V2-S3 stock adjustments, equity 3000, stock_adjustment journals.

Revision ID: 012_s3_stock_adjustments
Revises: 011_s2_stocktakes
Create Date: 2026-09-01

"""

from __future__ import annotations

import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012_s3_stock_adjustments"
down_revision: Union[str, Sequence[str], None] = "011_s2_stocktakes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_accounts_type", "accounts", type_="check")
    op.create_check_constraint(
        "ck_accounts_type",
        "accounts",
        "type IN ('asset', 'liability', 'income', 'expense', 'equity')",
    )

    op.drop_constraint("ck_journal_entries_document_type", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_document_type",
        "journal_entries",
        "document_type IN ('invoice', 'credit_note', 'bill', 'payment', 'stock_adjustment')",
    )

    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT 1 FROM accounts WHERE code = '3000'")).scalar()
    if existing is None:
        now = datetime.datetime.utcnow()
        accounts = sa.table(
            "accounts",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("type", sa.String),
            sa.column("is_system", sa.Boolean),
            sa.column("is_archived", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        )
        op.bulk_insert(
            accounts,
            [
                {
                    "id": uuid.uuid4(),
                    "code": "3000",
                    "name": "Opening balances",
                    "type": "equity",
                    "is_system": True,
                    "is_archived": False,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )

    op.create_table(
        "stock_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_stock_adjustments_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_stock_adjustments_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_adjustments"),
        sa.CheckConstraint(
            "status IN ('draft', 'completed', 'cancelled')",
            name="ck_stock_adjustments_status",
        ),
        sa.CheckConstraint(
            "reason IN ('opening', 'damage', 'theft', 'count_fix', 'write_off')",
            name="ck_stock_adjustments_reason",
        ),
    )
    op.create_index("ix_stock_adjustments_location_id", "stock_adjustments", ["location_id"])
    op.create_index(
        "ix_stock_adjustments_created_by_user_id",
        "stock_adjustments",
        ["created_by_user_id"],
    )

    op.create_table(
        "stock_adjustment_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adjustment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty_delta", sa.Integer(), nullable=False),
        sa.Column("unit_cost_zar", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["adjustment_id"],
            ["stock_adjustments.id"],
            name="fk_stock_adjustment_lines_adjustment_id_stock_adjustments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_stock_adjustment_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_adjustment_lines"),
        sa.CheckConstraint("qty_delta != 0", name="ck_stock_adjustment_lines_qty_delta"),
    )
    op.create_index(
        "ix_stock_adjustment_lines_adjustment_id",
        "stock_adjustment_lines",
        ["adjustment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_adjustment_lines_adjustment_id", table_name="stock_adjustment_lines")
    op.drop_table("stock_adjustment_lines")
    op.drop_index("ix_stock_adjustments_created_by_user_id", table_name="stock_adjustments")
    op.drop_index("ix_stock_adjustments_location_id", table_name="stock_adjustments")
    op.drop_table("stock_adjustments")

    op.execute(
        sa.text(
            "DELETE FROM journal_lines WHERE entry_id IN "
            "(SELECT id FROM journal_entries WHERE document_type = 'stock_adjustment')"
        )
    )
    op.execute(sa.text("DELETE FROM journal_entries WHERE document_type = 'stock_adjustment'"))
    op.execute(sa.text("DELETE FROM accounts WHERE code = '3000'"))

    op.drop_constraint("ck_journal_entries_document_type", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_document_type",
        "journal_entries",
        "document_type IN ('invoice', 'credit_note', 'bill', 'payment')",
    )
    op.drop_constraint("ck_accounts_type", "accounts", type_="check")
    op.create_check_constraint(
        "ck_accounts_type",
        "accounts",
        "type IN ('asset', 'liability', 'income', 'expense')",
    )
