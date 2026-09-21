"""Walk-in lookbooks: curated SKU shares with snapshotted prices.

Revision ID: 051_lookbooks
Revises: 050_cin7_sales_chain
Create Date: 2026-09-16

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "051_lookbooks"
down_revision: Union[str, Sequence[str], None] = "050_cin7_sales_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lookbooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("price_mode", sa.String(length=32), nullable=False),
        sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "price_mode IN ('retail', 'price_list', 'hidden')",
            name="ck_lookbooks_price_mode",
        ),
        sa.CheckConstraint(
            "(price_mode = 'price_list' AND price_list_id IS NOT NULL) OR "
            "(price_mode <> 'price_list' AND price_list_id IS NULL)",
            name="ck_lookbooks_price_list_id",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["price_list_id"], ["price_lists.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_lookbooks_token"),
    )
    op.create_index("ix_lookbooks_created_by_user_id", "lookbooks", ["created_by_user_id"])
    op.create_index("ix_lookbooks_customer_id", "lookbooks", ["customer_id"])
    op.create_index("ix_lookbooks_price_list_id", "lookbooks", ["price_list_id"])

    op.create_table(
        "lookbook_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("lookbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("snapshot_name", sa.Text(), nullable=False),
        sa.Column("snapshot_our_ref", sa.Text(), nullable=False),
        sa.Column("snapshot_unit_inc_vat", sa.Numeric(14, 2), nullable=True),
        sa.Column("snapshot_photo_key", sa.Text(), nullable=True),
        sa.CheckConstraint("position >= 0", name="ck_lookbook_items_position"),
        sa.ForeignKeyConstraint(["lookbook_id"], ["lookbooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lookbook_id", "sku_id", name="uq_lookbook_items_lookbook_sku"),
        sa.UniqueConstraint("lookbook_id", "position", name="uq_lookbook_items_lookbook_position"),
    )
    op.create_index("ix_lookbook_items_lookbook_id", "lookbook_items", ["lookbook_id"])


def downgrade() -> None:
    op.drop_index("ix_lookbook_items_lookbook_id", table_name="lookbook_items")
    op.drop_table("lookbook_items")
    op.drop_index("ix_lookbooks_price_list_id", table_name="lookbooks")
    op.drop_index("ix_lookbooks_customer_id", table_name="lookbooks")
    op.drop_index("ix_lookbooks_created_by_user_id", table_name="lookbooks")
    op.drop_table("lookbooks")
