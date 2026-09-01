"""V2-S13 SKU preferred supplier and lead time.

Revision ID: 018_v2_s13_sku_supplier
Revises: 017_v2_s10_customers_crm
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018_v2_s13_sku_supplier"
down_revision: Union[str, Sequence[str], None] = "017_v2_s10_customers_crm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("preferred_supplier_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "skus",
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_skus_preferred_supplier_id_suppliers",
        "skus",
        "suppliers",
        ["preferred_supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_skus_preferred_supplier_id_suppliers",
        "skus",
        type_="foreignkey",
    )
    op.drop_column("skus", "lead_time_days")
    op.drop_column("skus", "preferred_supplier_id")
