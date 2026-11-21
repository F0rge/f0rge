"""Invoices can be archived by staff and record where they were created.

Additive only (P-020): code from before this release keeps inserting invoices, which
get ``source = 'manual'`` from the server default. Cin7 imports keep ``is_archive``;
user archiving is the separate ``archived_at``.

The backfill marks earlier till sales by their journal memo. It runs once per team with
``app.tenant_id`` set, so it also reaches rows when RLS is forced for the migration owner.

Revision ID: 108_invoice_archive
Revises: 107_bill_approval_attachments
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "108_invoice_archive"
down_revision = "107_bill_approval_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_invoices", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "tax_invoices",
        sa.Column(
            "archived_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id", ondelete="SET NULL", name="fk_tax_invoices_archived_by_id_users"
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "tax_invoices",
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
    )
    op.execute("""DO $$
    DECLARE team uuid;
    BEGIN
        -- Filter by team as well: without forced RLS the policy does not narrow rows.
        FOR team IN SELECT id FROM teams LOOP
            PERFORM set_config('app.tenant_id', team::text, true);
            UPDATE tax_invoices SET source = 'till'
            WHERE team_id = team AND id IN (
                SELECT document_id FROM journal_entries
                WHERE team_id = team AND document_type = 'invoice'
                    AND memo LIKE 'Till tax invoice %'
            );
        END LOOP;
        PERFORM set_config('app.tenant_id', '', true);
    END $$""")


def downgrade() -> None:
    op.drop_column("tax_invoices", "source")
    op.drop_column("tax_invoices", "archived_by_id")
    op.drop_column("tax_invoices", "archived_at")
