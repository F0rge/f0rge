"""V2-S6 laybys, customer deposits 2300.

Revision ID: 014_v2_s6_laybys
Revises: 013_v2_s5_returns
Create Date: 2026-09-01

"""

from __future__ import annotations

import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014_v2_s6_laybys"
down_revision: Union[str, Sequence[str], None] = "013_v2_s5_returns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT 1 FROM accounts WHERE code = '2300'")).scalar()
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
                    "code": "2300",
                    "name": "Customer deposits",
                    "type": "liability",
                    "is_system": True,
                    "is_archived": False,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )

    op.create_table(
        "laybys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("layby_number", sa.Text(), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("hold_stock", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subtotal_ex_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_inc_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_laybys_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_laybys_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["tax_invoices.id"],
            name="fk_laybys_invoice_id_tax_invoices",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_laybys_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_laybys"),
        sa.UniqueConstraint("layby_number", name="uq_laybys_layby_number"),
        sa.CheckConstraint(
            "status IN ('open', 'ready', 'completed', 'cancelled')",
            name="ck_laybys_status",
        ),
    )
    op.create_index("ix_laybys_customer_id", "laybys", ["customer_id"])
    op.create_index("ix_laybys_location_id", "laybys", ["location_id"])
    op.create_index("ix_laybys_invoice_id", "laybys", ["invoice_id"])
    op.create_index("ix_laybys_created_by_user_id", "laybys", ["created_by_user_id"])

    op.create_table(
        "layby_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("layby_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_ex_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["layby_id"],
            ["laybys.id"],
            name="fk_layby_lines_layby_id_laybys",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_layby_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_layby_lines"),
        sa.CheckConstraint("qty > 0", name="ck_layby_lines_qty"),
    )
    op.create_index("ix_layby_lines_layby_id", "layby_lines", ["layby_id"])

    op.create_table(
        "layby_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("layby_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tender", sa.Text(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["layby_id"],
            ["laybys.id"],
            name="fk_layby_payments_layby_id_laybys",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_layby_payments"),
        sa.CheckConstraint("amount > 0", name="ck_layby_payments_amount"),
        sa.CheckConstraint(
            "tender IN ('cash', 'card')",
            name="ck_layby_payments_tender",
        ),
    )
    op.create_index("ix_layby_payments_layby_id", "layby_payments", ["layby_id"])


def downgrade() -> None:
    op.drop_index("ix_layby_payments_layby_id", table_name="layby_payments")
    op.drop_table("layby_payments")
    op.drop_index("ix_layby_lines_layby_id", table_name="layby_lines")
    op.drop_table("layby_lines")
    op.drop_index("ix_laybys_created_by_user_id", table_name="laybys")
    op.drop_index("ix_laybys_invoice_id", table_name="laybys")
    op.drop_index("ix_laybys_location_id", table_name="laybys")
    op.drop_index("ix_laybys_customer_id", table_name="laybys")
    op.drop_table("laybys")
    op.execute(sa.text("DELETE FROM accounts WHERE code = '2300'"))
