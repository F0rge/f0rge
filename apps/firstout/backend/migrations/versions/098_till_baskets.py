"""Keep each cashier's open till basket on the server.

Revision ID: 098_till_baskets
Revises: 097_till_hold_hours
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "098_till_baskets"
down_revision = "097_till_hold_hours"
branch_labels = None
depends_on = None

_TENANT_VALUE = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "till_baskets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text(_TENANT_VALUE),
        ),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("customer_id", UUID(as_uuid=True)),
        sa.Column("note", sa.String(500)),
        sa.Column("pick_id", UUID(as_uuid=True)),
        sa.Column("linked_pick_ids", JSONB, nullable=False),
        sa.Column("lines", JSONB, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_operation_id", UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_till_baskets_showroom_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "team_id", "location_id", "user_id", name="uq_till_baskets_user_showroom"
        ),
        sa.CheckConstraint("version >= 1", name="ck_till_baskets_version"),
    )
    op.create_index("ix_till_baskets_team_id", "till_baskets", ["team_id"])
    predicate = f"team_id = {_TENANT_VALUE}"
    op.execute(
        f"CREATE POLICY organisation_isolation ON till_baskets FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                   AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE till_baskets ENABLE ROW LEVEL SECURITY;
            ALTER TABLE till_baskets FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")


def downgrade() -> None:
    op.drop_table("till_baskets")
