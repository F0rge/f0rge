"""Archive reference records and retain scoped bulk-operation outcomes.

Revision ID: 085_record_workspaces
Revises: 084_party_archives

No existing rows, assignments, PDFs or purchase-order references are removed.
Apply runtime DML grants to the new table through the existing approved release
process before serving the new endpoints. This revision does not activate an
installation's tenant isolation stage or select a runtime role.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "085_record_workspaces"
down_revision = "084_party_archives"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("price_lists", "proformas"):
        op.add_column(
            table_name,
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(
            f"ix_{table_name}_team_id_is_archived", table_name, ["team_id", "is_archived"]
        )

    op.create_table(
        "record_workspace_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "selection", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "team_id", "actor_user_id", "request_id", name="uq_record_workspace_batch_request"
        ),
    )
    op.create_index("ix_record_workspace_batches_team_id", "record_workspace_batches", ["team_id"])
    predicate = "team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    op.execute(
        sa.text(
            "CREATE POLICY organisation_isolation ON record_workspace_batches "
            f"FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
        )
    )
    # Match 082: newly created tables inherit an already-enforced installation's
    # isolation, while compatibility installations retain their operator cutover.
    op.execute(
        sa.text("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class
                   WHERE oid='public.roles'::regclass
                   AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE record_workspace_batches ENABLE ROW LEVEL SECURITY;
            ALTER TABLE record_workspace_batches FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")
    )


def downgrade() -> None:
    # This removes new batch receipts/archive metadata, never domain records.
    # Release rollback must retain a backup if these new receipts are needed.
    op.drop_table("record_workspace_batches")
    for table_name in ("proformas", "price_lists"):
        op.drop_index(f"ix_{table_name}_team_id_is_archived", table_name=table_name)
        op.drop_column(table_name, "is_archived")
