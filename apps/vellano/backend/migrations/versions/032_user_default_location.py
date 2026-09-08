"""Per-user default till location.

Revision ID: 032_user_default_location
Revises: 031_two_step_transfers
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032_user_default_location"
down_revision: Union[str, Sequence[str], None] = "031_two_step_transfers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("default_location_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_users_default_location_id",
        "users",
        ["default_location_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_users_default_location_id_locations",
        "users",
        "locations",
        ["default_location_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET default_location_id = (
                SELECT id FROM locations
                WHERE lower(name) = 'bedfordview'
                  AND type = 'showroom'
                  AND NOT is_archived
                LIMIT 1
            )
            WHERE role = 'till'
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_users_default_location_id_locations",
        "users",
        type_="foreignkey",
    )
    op.drop_index("ix_users_default_location_id", table_name="users")
    op.drop_column("users", "default_location_id")
