"""Payments keep a bank reference and can be voided with a reason.

All columns are nullable, so code from before this release keeps inserting
payments unchanged after a rollback (P-020). The method stays in ``tender``;
``other`` fits its existing width.

Revision ID: 106_payment_reference_void
Revises: 105_quote_conversion
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "106_payment_reference_void"
down_revision = "105_quote_conversion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("reference", sa.Text(), nullable=True))
    op.add_column("payments", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "payments",
        sa.Column(
            "voided_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_payments_voided_by_id_users"),
            nullable=True,
        ),
    )
    op.add_column("payments", sa.Column("void_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "void_reason")
    op.drop_column("payments", "voided_by_id")
    op.drop_column("payments", "voided_at")
    op.drop_column("payments", "reference")
