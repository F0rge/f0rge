"""Customer-only Clerk identity approvals; preserve all customer and staff rows.

Revision ID: 083_portal_clerk_identity
Revises: 082_tenant_onboarding
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "083_portal_clerk_identity"
down_revision = "082_tenant_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("customers", "customer_portal_users"):
        if not any(
            item["column_names"] == ["team_id", "id"]
            for item in inspector.get_unique_constraints(table)
        ):
            op.create_unique_constraint("uq_" + table + "_team_id_id", table, ["team_id", "id"])

    def common():
        return [
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        ]

    # These are identity/capability directories, like users/memberships and the
    # provisioning directory. Business records remain tenant-owned FORCE RLS.
    op.create_table(
        "portal_access",
        *common(),
        sa.Column("clerk_user_id", sa.String(255), nullable=False),
        sa.Column(
            "organisation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "portal_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_portal_users.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.UniqueConstraint(
            "clerk_user_id", "organisation_id", name="uq_portal_access_subject_organisation"
        ),
    )
    op.create_index("ix_portal_access_clerk_user_id", "portal_access", ["clerk_user_id"])
    op.create_foreign_key(
        "fk_portal_access_customer_scope",
        "portal_access",
        "customers",
        ["organisation_id", "customer_id"],
        ["team_id", "id"],
    )
    op.create_foreign_key(
        "fk_portal_access_user_scope",
        "portal_access",
        "customer_portal_users",
        ["organisation_id", "portal_user_id"],
        ["team_id", "id"],
    )
    op.create_table(
        "portal_invitations",
        *common(),
        sa.Column(
            "organisation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime()),
        sa.Column("accepted_by_clerk_user_id", sa.String(255)),
        sa.Column("revoked_at", sa.DateTime()),
    )
    op.create_foreign_key(
        "fk_portal_invitation_customer_scope",
        "portal_invitations",
        "customers",
        ["organisation_id", "customer_id"],
        ["team_id", "id"],
    )


def downgrade() -> None:
    op.drop_table("portal_invitations")
    op.drop_table("portal_access")
