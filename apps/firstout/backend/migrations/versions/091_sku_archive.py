"""Add reversible SKU archive state without changing stock or historical references.

Revision ID: 091_sku_archive
Revises: 090_release_migration_receipts
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "091_sku_archive"
down_revision = "090_release_migration_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skus", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("skus", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("skus", sa.Column("archived_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_skus_archived_by_id_users",
        "skus",
        "users",
        ["archived_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_skus_team_id_is_archived", "skus", ["team_id", "is_archived"])


def downgrade() -> None:
    # Manual schema rollback removes archive metadata only; it never deletes SKUs,
    # recipes, stock or document lines. Automatic app rollback retains this schema.
    op.drop_index("ix_skus_team_id_is_archived", table_name="skus")
    op.drop_constraint("fk_skus_archived_by_id_users", "skus", type_="foreignkey")
    op.drop_column("skus", "archived_by_id")
    op.drop_column("skus", "archived_at")
    op.drop_column("skus", "is_archived")
