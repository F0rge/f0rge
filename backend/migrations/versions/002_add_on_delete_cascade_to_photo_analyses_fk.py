"""add_on_delete_cascade_to_photo_analyses_fk

Revision ID: a1b2c3d4e5f6
Revises: 5c4881e51b04
Create Date: 2026-05-16 00:00:00.000000

The baseline created photo_analyses.photo_id without ON DELETE CASCADE.
Photo.analysis uses cascade="all, delete-orphan" at the ORM level, but
direct DB-level deletes (e.g. admin scripts, test teardowns) would leave
orphan photo_analyses rows. This migration aligns the DB constraint with
the ORM intent.

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5c4881e51b04"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # Postgres names the unnamed FK constraint as <table>_<col>_fkey by default.
    op.drop_constraint(
        "photo_analyses_photo_id_fkey", "photo_analyses", type_="foreignkey"
    )
    op.create_foreign_key(
        "photo_analyses_photo_id_fkey",
        "photo_analyses",
        "photos",
        ["photo_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "photo_analyses_photo_id_fkey", "photo_analyses", type_="foreignkey"
    )
    op.create_foreign_key(
        "photo_analyses_photo_id_fkey",
        "photo_analyses",
        "photos",
        ["photo_id"],
        ["id"],
    )
