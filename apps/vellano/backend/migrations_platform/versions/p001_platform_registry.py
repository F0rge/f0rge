"""platform registry tables

Revision ID: p001_platform_registry
Revises:
Create Date: 2026-09-16

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p001_platform_registry"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("database_url_encrypted", sa.Text(), nullable=True),
        sa.Column("storage_prefix", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("provisioned_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.UniqueConstraint("storage_prefix"),
    )
    op.create_table(
        "tenant_hostnames",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("hostname", sa.Text(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname", name="uq_tenant_hostnames_hostname"),
    )
    op.create_index(
        op.f("ix_tenant_hostnames_tenant_id"),
        "tenant_hostnames",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "signups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False),
        sa.Column("trading_name", sa.String(length=200), nullable=True),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("owner_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verify_token_hash", sa.Text(), nullable=True),
        sa.Column("verify_expires_at", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("privacy_version", sa.Text(), nullable=False),
        sa.Column("authorised_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("verify_token_hash"),
    )
    op.create_index(op.f("ix_signups_email"), "signups", ["email"], unique=False)
    op.create_index(op.f("ix_signups_tenant_id"), "signups", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_signups_tenant_id"), table_name="signups")
    op.drop_index(op.f("ix_signups_email"), table_name="signups")
    op.drop_table("signups")
    op.drop_index(op.f("ix_tenant_hostnames_tenant_id"), table_name="tenant_hostnames")
    op.drop_table("tenant_hostnames")
    op.drop_table("tenants")
