"""Preserve staff identities and home grants while adding organisation membership.

Revision ID: 079_tenant_identity
Revises: 078_password_reset
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "079_tenant_identity"
down_revision = "078_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    count = bind.scalar(sa.text("SELECT count(*) FROM teams"))
    if count > 1:
        raise RuntimeError("Tenant backfill requires an inventoried single bootstrap team")
    if count == 0:
        bind.execute(
            sa.text(
                "INSERT INTO teams (id,name,created_at,updated_at) VALUES (gen_random_uuid(),'Firstout',now(),now())"
            )
        )
    op.add_column("teams", sa.Column("slug", sa.String(63), nullable=True))
    op.add_column(
        "teams", sa.Column("status", sa.String(24), nullable=False, server_default="active")
    )
    op.add_column("teams", sa.Column("clerk_org_id", sa.String(255), nullable=True))
    bind.execute(sa.text("UPDATE teams SET slug = 'firstout' WHERE slug IS NULL"))
    op.alter_column("teams", "slug", nullable=False)
    op.create_unique_constraint("uq_teams_slug", "teams", ["slug"])
    op.create_unique_constraint("uq_teams_clerk_org_id", "teams", ["clerk_org_id"])
    op.add_column("users", sa.Column("clerk_user_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_users_clerk_user_id", "users", ["clerk_user_id"])
    op.create_table(
        "memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("permission_source", sa.String(32), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("is_legacy_home", sa.Boolean(), nullable=False),
        sa.Column(
            "default_location_id",
            UUID(as_uuid=True),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "team_id", name="uq_memberships_user_team"),
    )
    op.create_index(
        "uq_memberships_legacy_home",
        "memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_legacy_home"),
    )
    bind.execute(
        sa.text("""INSERT INTO memberships
        (id,user_id,team_id,role,permission_source,is_disabled,is_legacy_home,default_location_id,created_at,updated_at)
        SELECT gen_random_uuid(),id,team_id,role,'legacy',is_disabled,true,default_location_id,now(),now() FROM users""")
    )
    for name, value in (("label_width_mm", "100"), ("label_height_mm", "60")):
        op.add_column(
            "team_settings", sa.Column(name, sa.Integer(), nullable=False, server_default=value)
        )
    for name, value in (
        ("label_show_name", "true"),
        ("label_show_reference", "true"),
        ("label_show_barcode", "true"),
        ("label_show_logo", "false"),
    ):
        op.add_column(
            "team_settings",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text(value)),
        )
    op.create_table(
        "clerk_webhook_events",
        sa.Column("svix_id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("clerk_webhook_events")
    for name in (
        "label_width_mm",
        "label_height_mm",
        "label_show_name",
        "label_show_reference",
        "label_show_barcode",
        "label_show_logo",
    ):
        op.drop_column("team_settings", name)
    op.drop_table("memberships")
    op.drop_constraint("uq_users_clerk_user_id", "users")
    op.drop_column("users", "clerk_user_id")
    for name in ("uq_teams_slug", "uq_teams_clerk_org_id"):
        op.drop_constraint(name, "teams")
    for name in ("clerk_org_id", "status", "slug"):
        op.drop_column("teams", name)
