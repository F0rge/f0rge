"""Named price lists and customer assignment.

Revision ID: 044_price_lists
Revises: 043_company_settings_wave2
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "044_price_lists"
down_revision: Union[str, Sequence[str], None] = "043_company_settings_wave2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "price_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_ex_vat", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["price_list_id"], ["price_lists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("price_list_id", "sku_id", name="uq_price_list_items_list_sku"),
        sa.CheckConstraint("unit_ex_vat > 0", name="ck_price_list_items_unit_ex_vat_positive"),
    )
    op.create_index("ix_price_list_items_price_list_id", "price_list_items", ["price_list_id"])
    op.create_index("ix_price_list_items_sku_id", "price_list_items", ["sku_id"])
    op.add_column(
        "customers",
        sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_customers_price_list_id",
        "customers",
        "price_lists",
        ["price_list_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_customers_price_list_id", "customers", ["price_list_id"])


def downgrade() -> None:
    op.drop_index("ix_customers_price_list_id", table_name="customers")
    op.drop_constraint("fk_customers_price_list_id", "customers", type_="foreignkey")
    op.drop_column("customers", "price_list_id")
    op.drop_index("ix_price_list_items_sku_id", table_name="price_list_items")
    op.drop_index("ix_price_list_items_price_list_id", table_name="price_list_items")
    op.drop_table("price_list_items")
    op.drop_table("price_lists")
