"""Permission catalog roles and role_permissions.

Revision ID: 033_roles_permissions
Revises: 032_user_default_location
Create Date: 2026-09-01

"""

from __future__ import annotations

import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.permissions import (
    ROLE_PRESET_NAMES,
    ROLE_PRESETS,
    SLUG_OWNER,
    SYSTEM_ROLE_SLUGS,
)

revision: str = "033_roles_permissions"
down_revision: Union[str, Sequence[str], None] = "032_user_default_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLE_NS = uuid.UUID("00000000-0000-4000-8000-000000000033")


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "is_owner_preset",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("slug", name="uq_roles_slug"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_role_permissions_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "key", name="pk_role_permissions"),
    )
    op.drop_constraint("ck_users_role", "users", type_="check")

    now = datetime.datetime.utcnow()
    bind = op.get_bind()
    for slug in SYSTEM_ROLE_SLUGS:
        role_id = uuid.uuid5(_ROLE_NS, slug)
        bind.execute(
            sa.text(
                """
                INSERT INTO roles (
                    id, slug, name, is_system, is_owner_preset, created_at, updated_at
                )
                VALUES (
                    :id, :slug, :name, true, :is_owner_preset, :created_at, :updated_at
                )
                """
            ),
            {
                "id": role_id,
                "slug": slug,
                "name": ROLE_PRESET_NAMES[slug],
                "is_owner_preset": slug == SLUG_OWNER,
                "created_at": now,
                "updated_at": now,
            },
        )
        for key in sorted(ROLE_PRESETS[slug]):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, key)
                    VALUES (:role_id, :key)
                    """
                ),
                {"role_id": role_id, "key": key},
            )


def downgrade() -> None:
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('owner', 'buyer', 'warehouse', 'till', 'books')",
    )
    op.drop_table("role_permissions")
    op.drop_table("roles")
