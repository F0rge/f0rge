"""Remember the cost stock left the shelf at: layby hold cost and invoice line cost of goods.

Nullable columns only: rows written before this release keep NULL and their readers fall back
to the location's current average, as before.

Revision ID: 112_sale_line_unit_cost
Revises: 111_sku_curated_catalogue
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "112_sale_line_unit_cost"
down_revision = "111_sku_curated_catalogue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "layby_lines",
        sa.Column("hold_unit_cost_zar", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "invoice_lines",
        sa.Column("unit_cost_zar", sa.Numeric(18, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoice_lines", "unit_cost_zar")
    op.drop_column("layby_lines", "hold_unit_cost_zar")
