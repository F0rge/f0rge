"""Keep enough precision for an exact VAT-inclusive catalogue retail price.

Revision ID: 118_sku_retail_precision
Revises: 117_sku_swatch_hex
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "118_sku_retail_precision"
down_revision = "117_sku_swatch_hex"
branch_labels = None
depends_on = None

_CENT_CHECK = "ck_skus_retail_ex_vat_fits_cents"


def upgrade() -> None:
    op.alter_column(
        "skus",
        "retail_ex_vat",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Numeric(14, 4),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Validate all rows before shrinking the column so no price is silently rounded.
    op.create_check_constraint(_CENT_CHECK, "skus", "retail_ex_vat = round(retail_ex_vat, 2)")
    op.alter_column(
        "skus",
        "retail_ex_vat",
        existing_type=sa.Numeric(14, 4),
        type_=sa.Numeric(12, 2),
        existing_nullable=True,
    )
    op.drop_constraint(_CENT_CHECK, "skus", type_="check")
