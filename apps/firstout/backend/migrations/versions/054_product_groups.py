"""Group operational SKUs into explicit storefront variants.

Revision ID: 054_product_groups
Revises: 053_storefront_publication
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "054_product_groups"
down_revision: Union[str, Sequence[str], None] = "053_storefront_publication"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("storefront_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "product_group_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("option_signature", sa.String(length=2048), nullable=False),
        sa.ForeignKeyConstraint(["product_group_id"], ["product_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_sku_id", name="uq_product_group_variants_sku"),
        sa.UniqueConstraint(
            "product_group_id", "option_signature", name="uq_product_group_variants_combination"
        ),
    )
    op.create_index(
        "ix_product_group_variants_group_id", "product_group_variants", ["product_group_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_product_group_variants_group_id", table_name="product_group_variants")
    op.drop_table("product_group_variants")
    op.drop_table("product_groups")
