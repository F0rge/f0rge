"""B6 monthly repeating invoices (manual run only).

Revision ID: 027_repeating_invoices
Revises: 026_bank_rules
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "027_repeating_invoices"
down_revision: Union[str, Sequence[str], None] = "026_bank_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repeating_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column("next_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "day_of_month >= 1 AND day_of_month <= 28",
            name="ck_repeating_invoices_day_of_month",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_repeating_invoices_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_repeating_invoices_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repeating_invoices"),
    )
    op.create_index(
        "ix_repeating_invoices_customer_id",
        "repeating_invoices",
        ["customer_id"],
    )
    op.create_index(
        "ix_repeating_invoices_created_by",
        "repeating_invoices",
        ["created_by"],
    )

    op.create_table(
        "repeating_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_ex_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("qty > 0", name="ck_repeating_invoice_lines_qty"),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["repeating_invoices.id"],
            name="fk_repeating_invoice_lines_schedule_id_repeating_invoices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repeating_invoice_lines"),
    )
    op.create_index(
        "ix_repeating_invoice_lines_schedule_id",
        "repeating_invoice_lines",
        ["schedule_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_repeating_invoice_lines_schedule_id",
        table_name="repeating_invoice_lines",
    )
    op.drop_table("repeating_invoice_lines")
    op.drop_index("ix_repeating_invoices_created_by", table_name="repeating_invoices")
    op.drop_index("ix_repeating_invoices_customer_id", table_name="repeating_invoices")
    op.drop_table("repeating_invoices")
