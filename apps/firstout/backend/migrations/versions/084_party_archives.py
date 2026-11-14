"""Add archive state without changing customer or supplier records.

Revision ID: 084_party_archives
Revises: 083_portal_clerk_identity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "084_party_archives"
down_revision = "083_portal_clerk_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("customers", "suppliers"):
        op.add_column(
            table_name,
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(
            f"ix_{table_name}_team_id_is_archived",
            table_name,
            ["team_id", "is_archived"],
        )


def downgrade() -> None:
    for table_name in ("suppliers", "customers"):
        op.drop_index(f"ix_{table_name}_team_id_is_archived", table_name=table_name)
        op.drop_column(table_name, "is_archived")
