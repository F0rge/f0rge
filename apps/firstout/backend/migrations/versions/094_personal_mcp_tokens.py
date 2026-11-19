"""Store per-membership MCP credentials and recent activity.

Revision ID: 094_personal_mcp_tokens
Revises: 093_till_price_list_policy
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "094_personal_mcp_tokens"
down_revision = "093_till_price_list_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("digest", sa.String(64)),
        sa.Column("suffix", sa.String(4), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["user_id", "team_id"],
            ["memberships.user_id", "memberships.team_id"],
            name="fk_mcp_tokens_membership",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("team_id", "digest", name="uq_mcp_tokens_team_digest"),
        sa.UniqueConstraint("team_id", "user_id", "id", name="uq_mcp_tokens_owner_id"),
    )
    op.create_index("ix_mcp_tokens_team_id", "mcp_tokens", ["team_id"])
    op.create_index(
        "ix_mcp_tokens_owner_created", "mcp_tokens", ["team_id", "user_id", "created_at"]
    )
    op.create_table(
        "mcp_token_activity",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_name", sa.String(80), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("source", sa.String(12), nullable=False),
        sa.Column("result", sa.String(12), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id", "user_id", "token_id"],
            ["mcp_tokens.team_id", "mcp_tokens.user_id", "mcp_tokens.id"],
            name="fk_mcp_token_activity_owner",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_mcp_token_activity_team_id", "mcp_token_activity", ["team_id"])
    op.create_index(
        "ix_mcp_token_activity_owner_time",
        "mcp_token_activity",
        ["team_id", "user_id", "occurred_at"],
    )

    predicate = "team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    for table in ("mcp_tokens", "mcp_token_activity"):
        op.execute(
            f"CREATE POLICY organisation_isolation ON {table} FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
        )
        # Follow the existing isolation stage. Cutover enables matching policies for compatibility databases.
        op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                       AND relrowsecurity AND relforcerowsecurity) THEN
                ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            END IF;
        END $$""")


def downgrade() -> None:
    op.drop_table("mcp_token_activity")
    op.drop_table("mcp_tokens")
