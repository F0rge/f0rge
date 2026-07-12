"""meal_tags

Revision ID: 038
Revises: 037
Create Date: 2026-07-12 00:00:00.000000

Meal tagging + photo provenance + tagged_meal_mode preference (#307).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.sql.social_rls import MEAL_TAGS_RLS_STATEMENTS

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_MEAL_TAGS_RLS = list(MEAL_TAGS_RLS_STATEMENTS)


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column(
            "source_photo_id",
            sa.Integer(),
            sa.ForeignKey("photos.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "photos",
        sa.Column(
            "tagged_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "uq_photos_user_source",
        "photos",
        ["user_id", "source_photo_id"],
        unique=True,
        postgresql_where=sa.text("source_photo_id IS NOT NULL"),
    )

    op.create_table(
        "meal_tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "source_photo_id",
            sa.Integer(),
            sa.ForeignKey("photos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tagger_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tagged_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="pending_analysis", nullable=False),
        sa.Column("source_label", sa.Text(), nullable=True),
        sa.Column("source_dish_name", sa.Text(), nullable=True),
        sa.Column("source_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "delivered_photo_id",
            sa.Integer(),
            sa.ForeignKey("photos.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending_analysis','pending_approval','delivered','declined','cancelled')",
            name="ck_meal_tags_status",
        ),
        sa.CheckConstraint("tagger_id <> tagged_user_id", name="ck_meal_tags_not_self"),
        sa.UniqueConstraint("source_photo_id", "tagged_user_id", name="uq_meal_tags_pair"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_tags_tagged_user", "meal_tags", ["tagged_user_id"])
    op.create_index("ix_meal_tags_tagger", "meal_tags", ["tagger_id"])
    op.create_index("ix_meal_tags_source", "meal_tags", ["source_photo_id"])

    for stmt in _MEAL_TAGS_RLS:
        op.execute(sa.text(stmt))

    op.add_column(
        "user_settings",
        sa.Column("tagged_meal_mode", sa.Text(), server_default="approve", nullable=False),
    )
    op.create_check_constraint(
        "ck_user_settings_tagged_meal_mode",
        "user_settings",
        "tagged_meal_mode IN ('approve','auto')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_settings_tagged_meal_mode", "user_settings", type_="check")
    op.drop_column("user_settings", "tagged_meal_mode")

    for stmt in reversed(_MEAL_TAGS_RLS):
        if "CREATE POLICY" in stmt:
            policy_name = stmt.split("CREATE POLICY ")[1].split(" ")[0]
            op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON meal_tags"))
    op.execute(sa.text("ALTER TABLE meal_tags DISABLE ROW LEVEL SECURITY"))
    op.drop_table("meal_tags")

    op.drop_index("uq_photos_user_source", table_name="photos")
    op.drop_column("photos", "tagged_by_user_id")
    op.drop_column("photos", "source_photo_id")
