"""Live commerce source scans and durable authorized repair commands.

Revision ID: 061_live_commerce_exceptions
Revises: 060_storefront_exceptions
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "061_live_commerce_exceptions"
down_revision: Union[str, Sequence[str], None] = "060_storefront_exceptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_AUDIT_CHECK = "outcome IN ('repaired', 'already_resolved', 'denied', 'needs_provider')"
NEW_AUDIT_CHECK = "outcome IN ('repaired', 'already_resolved', 'denied', 'needs_provider', 'repair_requested', 'repair_failed')"


def upgrade() -> None:
    op.add_column(
        "storefront_commerce_exceptions",
        sa.Column("source", sa.String(16), nullable=False, server_default="fixture"),
    )
    op.add_column(
        "storefront_commerce_exceptions",
        sa.Column("source_received_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "storefront_commerce_exceptions",
        sa.Column("repair_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_storefront_exception_source",
        "storefront_commerce_exceptions",
        "source IN ('fixture', 'commerce')",
    )
    op.create_index(
        "uq_storefront_live_exception_identity",
        "storefront_commerce_exceptions",
        ["company_id", "kind", "correlation_id"],
        unique=True,
        postgresql_where=sa.text("source = 'commerce'"),
    )
    op.drop_constraint(
        "ck_storefront_exception_audit_outcome", "storefront_exception_audits", type_="check"
    )
    op.create_check_constraint(
        "ck_storefront_exception_audit_outcome", "storefront_exception_audits", NEW_AUDIT_CHECK
    )
    op.create_table(
        "storefront_exception_projections",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("company_id"),
    )
    op.create_table(
        "storefront_exception_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exception_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("detail", sa.String(255), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["exception_id"], ["storefront_commerce_exceptions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["audit_id"], ["storefront_exception_audits.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id"),
        sa.UniqueConstraint(
            "exception_id", "idempotency_key", name="uq_storefront_exception_command_key"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'repaired', 'not_repaired')",
            name="ck_storefront_exception_command_status",
        ),
    )


def downgrade() -> None:
    # A rollback must not discard authorizations or rewrite append-only repair history.
    recorded = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM storefront_exception_commands"))
        .scalar_one()
    )
    if recorded:
        raise RuntimeError(
            "Preserve recorded commerce repair commands; roll back application code without dropping this additive schema"
        )
    op.drop_table("storefront_exception_commands")
    op.drop_table("storefront_exception_projections")
    op.drop_constraint(
        "ck_storefront_exception_audit_outcome", "storefront_exception_audits", type_="check"
    )
    op.create_check_constraint(
        "ck_storefront_exception_audit_outcome", "storefront_exception_audits", OLD_AUDIT_CHECK
    )
    op.drop_index(
        "uq_storefront_live_exception_identity", table_name="storefront_commerce_exceptions"
    )
    op.drop_constraint(
        "ck_storefront_exception_source", "storefront_commerce_exceptions", type_="check"
    )
    op.drop_column("storefront_commerce_exceptions", "repair_pending")
    op.drop_column("storefront_commerce_exceptions", "source_received_at")
    op.drop_column("storefront_commerce_exceptions", "source")
