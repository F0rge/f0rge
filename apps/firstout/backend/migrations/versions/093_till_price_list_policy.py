"""Allow approved price lists to require a listed price at the till."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "093_till_price_list_policy"
down_revision = "092_till_no_stock_required"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "price_lists",
        sa.Column(
            "till_require_listed_price", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("price_lists", "till_require_listed_price")
