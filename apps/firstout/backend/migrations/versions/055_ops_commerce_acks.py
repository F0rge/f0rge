"""Record channel commitments reflected in operational stock.

Revision ID: 055_ops_commerce_acks
Revises: 054_product_groups
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "055_ops_commerce_acks"
down_revision: Union[str, Sequence[str], None] = "054_product_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ops_commerce_acknowledgements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("commitment_id", sa.String(length=255), nullable=False),
        sa.Column("source_sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_ops_commerce_acknowledgements_quantity"),
        sa.ForeignKeyConstraint(["source_sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("commitment_id"),
    )
    op.create_index(
        "ix_ops_commerce_acknowledgements_source_sku_id",
        "ops_commerce_acknowledgements",
        ["source_sku_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ops_commerce_acknowledgements_source_sku_id",
        table_name="ops_commerce_acknowledgements",
    )
    op.drop_table("ops_commerce_acknowledgements")
