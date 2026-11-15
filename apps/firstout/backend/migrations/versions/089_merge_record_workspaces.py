"""Join inventory precision and record workspace migrations without data changes.

Revision ID: 089_merge_record_workspaces
Revises: 088_archive_sales_precision, 085_record_workspaces

Both existing branches retain their identities. Alembic applies the missing
branch before reaching this single head; the merge itself performs no DDL/DML.
"""

from __future__ import annotations

revision = "089_merge_record_workspaces"
down_revision = ("088_archive_sales_precision", "085_record_workspaces")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
