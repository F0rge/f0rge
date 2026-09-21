"""PO pending_approval and rejected statuses.

Revision ID: 045_po_approval_statuses
Revises: 044_price_lists
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "045_po_approval_statuses"
down_revision: Union[str, Sequence[str], None] = "044_price_lists"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_purchase_orders_status", "purchase_orders", type_="check")
    op.create_check_constraint(
        "ck_purchase_orders_status",
        "purchase_orders",
        "status IN ('pending_approval', 'rejected', 'open', 'on_water', 'landed', 'received')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_purchase_orders_status", "purchase_orders", type_="check")
    op.create_check_constraint(
        "ck_purchase_orders_status",
        "purchase_orders",
        "status IN ('open', 'on_water', 'landed', 'received')",
    )
