"""Retain non-tenant deployment acknowledgements without customer data.

Revision ID: 090_release_migration_receipts
Revises: 089_merge_record_workspaces

The migration identity writes these operational receipts. The CD migration
runner grants only SELECT to the configured application runtime role. No
customer, organisation, token or credential is stored here; tenant RLS does
not apply. Application rollback retains the table and every receipt.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "090_release_migration_receipts"
down_revision = "089_merge_record_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "release_migration_receipts",
        sa.Column("source_commit", sa.String(40), primary_key=True),
        sa.Column("schema_revision", sa.String(64), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("from_revision", sa.String(64), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.execute("REVOKE ALL ON TABLE release_migration_receipts FROM PUBLIC")


def downgrade() -> None:
    # Not used by automatic recovery: dropping operational history needs its
    # own recovery decision, just as dropping application data does.
    op.drop_table("release_migration_receipts")
