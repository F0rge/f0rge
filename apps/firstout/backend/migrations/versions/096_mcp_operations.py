"""Add tenant-isolated MCP write receipts and review requests."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "096_mcp_operations"
down_revision = "095_till_held_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_operations",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(
            "team_id",
            UUID(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
        ),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("token_id", UUID(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("request_id", UUID(), nullable=False),
        sa.Column("action_name", sa.String(80), nullable=False),
        sa.Column("arguments", JSONB(), nullable=False),
        sa.Column("preview", JSONB()),
        sa.Column("result", JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", UUID()),
        sa.ForeignKeyConstraint(
            ["team_id", "user_id", "token_id"],
            ["mcp_tokens.team_id", "mcp_tokens.user_id", "mcp_tokens.id"],
            name="fk_mcp_operations_owner",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("team_id", "token_id", "request_id", name="uq_mcp_operations_request"),
    )
    op.create_index("ix_mcp_operations_team_id", "mcp_operations", ["team_id"])
    op.create_table(
        "mcp_action_activity",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(
            "team_id",
            UUID(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
        ),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("token_id", UUID(), nullable=False),
        sa.Column("token_name", sa.String(80), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("action_name", sa.String(80)),
        sa.Column("operation_id", UUID()),
        sa.Column("source", sa.String(12), nullable=False),
        sa.Column("result", sa.String(12), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id", "user_id", "token_id"],
            ["mcp_tokens.team_id", "mcp_tokens.user_id", "mcp_tokens.id"],
            name="fk_mcp_action_activity_owner",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_mcp_action_activity_team_id", "mcp_action_activity", ["team_id"])
    op.create_index(
        "ix_mcp_action_activity_owner_time",
        "mcp_action_activity",
        ["team_id", "user_id", "occurred_at"],
    )
    predicate = "team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    for table in ("mcp_operations", "mcp_action_activity"):
        op.execute(
            f"CREATE POLICY organisation_isolation ON {table} FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
        )
        op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.mcp_tokens'::regclass
                       AND relrowsecurity AND relforcerowsecurity) THEN
                ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            END IF;
        END $$""")


def downgrade() -> None:
    op.drop_table("mcp_action_activity")
    op.drop_table("mcp_operations")
