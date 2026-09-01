"""V2-S5 stock returns / RMA.

Revision ID: 013_v2_s5_returns
Revises: 012_s3_stock_adjustments
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_v2_s5_returns"
down_revision: Union[str, Sequence[str], None] = "012_s3_stock_adjustments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoice_lines",
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoice_lines_sku_id_skus",
        "invoice_lines",
        "skus",
        ["sku_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "stock_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("return_number", sa.Text(), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credit_note_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["tax_invoices.id"],
            name="fk_stock_returns_invoice_id_tax_invoices",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_stock_returns_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["credit_note_id"],
            ["credit_notes.id"],
            name="fk_stock_returns_credit_note_id_credit_notes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_stock_returns_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_returns"),
        sa.UniqueConstraint("return_number", name="uq_stock_returns_return_number"),
        sa.CheckConstraint(
            "status IN ('draft', 'completed', 'cancelled')",
            name="ck_stock_returns_status",
        ),
        sa.CheckConstraint(
            "reason IN ('damaged', 'unwanted', 'wrong_item', 'other')",
            name="ck_stock_returns_reason",
        ),
        sa.CheckConstraint(
            "disposition IN ('restock', 'write_off')",
            name="ck_stock_returns_disposition",
        ),
    )
    op.create_index("ix_stock_returns_invoice_id", "stock_returns", ["invoice_id"])
    op.create_index("ix_stock_returns_location_id", "stock_returns", ["location_id"])
    op.create_index("ix_stock_returns_credit_note_id", "stock_returns", ["credit_note_id"])
    op.create_index(
        "ix_stock_returns_created_by_user_id",
        "stock_returns",
        ["created_by_user_id"],
    )

    op.create_table(
        "stock_return_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["return_id"],
            ["stock_returns.id"],
            name="fk_stock_return_lines_return_id_stock_returns",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_line_id"],
            ["invoice_lines.id"],
            name="fk_stock_return_lines_invoice_line_id_invoice_lines",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_stock_return_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_return_lines"),
        sa.CheckConstraint("qty > 0", name="ck_stock_return_lines_qty"),
    )
    op.create_index("ix_stock_return_lines_return_id", "stock_return_lines", ["return_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_return_lines_return_id", table_name="stock_return_lines")
    op.drop_table("stock_return_lines")
    op.drop_index("ix_stock_returns_created_by_user_id", table_name="stock_returns")
    op.drop_index("ix_stock_returns_credit_note_id", table_name="stock_returns")
    op.drop_index("ix_stock_returns_location_id", table_name="stock_returns")
    op.drop_index("ix_stock_returns_invoice_id", table_name="stock_returns")
    op.drop_table("stock_returns")
    op.drop_constraint("fk_invoice_lines_sku_id_skus", "invoice_lines", type_="foreignkey")
    op.drop_column("invoice_lines", "sku_id")
