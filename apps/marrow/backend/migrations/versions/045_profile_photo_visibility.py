"""profile_photo_visibility

Revision ID: 045
Revises: 044
Create Date: 2026-07-18 00:00:00.000000

Profile photo visibility (#403): photos.hidden_at, per-photo explicit diet
tags (photo_diet_tags), and the profile tag-filter settings pair.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

# Frozen copy of the stock f0rge_db.rls.enable_tenant_isolation DDL as of 045 —
# do NOT import live app/lib code here (021 convention: new tables get their
# RLS inline in their own migration).
_PHOTO_DIET_TAGS_RLS: tuple[str, ...] = (
    "ALTER TABLE photo_diet_tags ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE photo_diet_tags FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY tenant_isolation ON photo_diet_tags
        FOR ALL
        USING (user_id = current_setting('app.user_id', true)::uuid)
        WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
    """,
)


def upgrade() -> None:
    op.add_column("photos", sa.Column("hidden_at", sa.DateTime(), nullable=True))

    op.add_column(
        "user_settings",
        sa.Column("profile_tag_filter_mode", sa.Text(), server_default="off", nullable=False),
    )
    op.create_check_constraint(
        "ck_user_settings_profile_tag_filter_mode",
        "user_settings",
        "profile_tag_filter_mode IN ('off','hide','show_only')",
    )
    op.add_column(
        "user_settings",
        sa.Column("profile_filter_tags", sa.Text(), server_default="", nullable=False),
    )

    op.create_table(
        "photo_diet_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "photo_id",
            sa.Integer(),
            sa.ForeignKey("photos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.UniqueConstraint("photo_id", "key", name="uq_photo_diet_tags_photo_id_key"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_photo_diet_tags_user_id", "photo_diet_tags", ["user_id"])

    for stmt in _PHOTO_DIET_TAGS_RLS:
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON photo_diet_tags"))
    op.execute(sa.text("ALTER TABLE photo_diet_tags DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_photo_diet_tags_user_id", table_name="photo_diet_tags")
    op.drop_table("photo_diet_tags")

    op.drop_column("user_settings", "profile_filter_tags")
    op.drop_constraint("ck_user_settings_profile_tag_filter_mode", "user_settings", type_="check")
    op.drop_column("user_settings", "profile_tag_filter_mode")

    op.drop_column("photos", "hidden_at")
