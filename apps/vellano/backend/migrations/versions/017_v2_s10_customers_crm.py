"""V2-S10 customers CRM columns.

Revision ID: 017_v2_s10_customers_crm
Revises: 016_v2_s9_till_discount
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_v2_s10_customers_crm"
down_revision: Union[str, Sequence[str], None] = "016_v2_s9_till_discount"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "customer_type",
            sa.String(length=32),
            nullable=False,
            server_default="retail",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "price_tier",
            sa.String(length=64),
            nullable=False,
            server_default="standard",
        ),
    )
    op.add_column(
        "customers",
        sa.Column("phone", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_customers_customer_type",
        "customers",
        "customer_type IN ('retail', 'trade')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_customers_customer_type", "customers", type_="check")
    op.drop_column("customers", "phone")
    op.drop_column("customers", "price_tier")
    op.drop_column("customers", "customer_type")
