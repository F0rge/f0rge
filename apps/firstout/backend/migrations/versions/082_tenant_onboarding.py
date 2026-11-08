"""Durable public provisioning attempts and scoped invitation approvals.

Revision ID: 082_tenant_onboarding
Revises: 081_tenant_rls
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "082_tenant_onboarding"
down_revision = "081_tenant_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    def common():
        return [
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        ]

    op.create_table(
        "tenant_provisioning_attempts",
        *common(),
        sa.Column("clerk_user_id", sa.String(255), nullable=False, index=True),
        sa.Column("slug", sa.String(63), nullable=False, unique=True),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("clerk_org_id", sa.String(255)),
        sa.Column(
            "result_team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
        ),
    )
    op.create_table(
        "tenant_invitations",
        *common(),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("clerk_invitation_id", sa.String(255)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index("ix_tenant_invitations_team_id", "tenant_invitations", ["team_id"])
    op.create_index(
        "uq_pending_tenant_invitation_email",
        "tenant_invitations",
        ["team_id", "email"],
        unique=True,
        postgresql_where=sa.text("status='pending'"),
    )
    predicate = "team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    op.execute(
        sa.text(
            f"CREATE POLICY organisation_isolation ON tenant_invitations FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
        )
    )
    # An already-enforced deployment must protect newly added tables immediately.
    # A compatibility installation still activates all policies via tenant_cutover.
    op.execute(
        sa.text("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE relname='roles' AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE tenant_invitations ENABLE ROW LEVEL SECURITY;
            ALTER TABLE tenant_invitations FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")
    )


def downgrade() -> None:
    op.drop_table("tenant_invitations")
    op.drop_table("tenant_provisioning_attempts")
