"""Bills get a due date, approval, user archiving, notes and many attachments.

Additive only (P-020): code from before this release keeps inserting bills, which
get ``approval_status = 'approved'`` from the server default and post as before.
``pdf_storage_key`` stays and is copied into ``bill_attachments``. The unused
``team_settings.auto_process_exact_supplier_invoices`` column stays until a later
release drops it.

The backfill runs once per team with ``app.tenant_id`` set, so it also reaches
rows when RLS is forced on ``bills`` for the migration owner.

Revision ID: 107_bill_approval_attachments
Revises: 106_payment_reference_void
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "107_bill_approval_attachments"
down_revision = "106_payment_reference_void"
branch_labels = None
depends_on = None

_TENANT_VALUE = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column("bills", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column(
        "bills",
        sa.Column("approval_status", sa.String(32), nullable=False, server_default="approved"),
    )
    op.create_check_constraint(
        "ck_bills_approval_status",
        "bills",
        "approval_status IN ('draft', 'awaiting_approval', 'approved')",
    )
    op.add_column("bills", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "bills",
        sa.Column(
            "archived_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_bills_archived_by_id_users"),
            nullable=True,
        ),
    )
    op.add_column("bills", sa.Column("notes", sa.Text(), nullable=True))

    # 080 gave bills a (team_id, id) key; create it only where one is missing.
    if not any(
        item["column_names"] == ["team_id", "id"]
        for item in sa.inspect(op.get_bind()).get_unique_constraints("bills")
    ):
        op.create_unique_constraint("uq_bills_team_id_id", "bills", ["team_id", "id"])
    op.create_table(
        "bill_attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text(_TENANT_VALUE),
        ),
        sa.Column("bill_id", UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "uploaded_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # The bill must belong to the attachment's organisation; a plain FK ignores RLS.
        sa.ForeignKeyConstraint(
            ["team_id", "bill_id"],
            ["bills.team_id", "bills.id"],
            name="fk_bill_attachments_bill_tenant",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_bill_attachments_team_id", "bill_attachments", ["team_id"])
    op.create_index("ix_bill_attachments_bill_id", "bill_attachments", ["bill_id"])
    predicate = f"team_id = {_TENANT_VALUE}"
    op.execute(
        f"CREATE POLICY organisation_isolation ON bill_attachments FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                   AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE bill_attachments ENABLE ROW LEVEL SECURITY;
            ALTER TABLE bill_attachments FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")

    op.execute("""DO $$
    DECLARE team uuid;
    BEGIN
        -- Filter by team as well: without forced RLS the policy does not narrow rows.
        FOR team IN SELECT id FROM teams LOOP
            PERFORM set_config('app.tenant_id', team::text, true);
            UPDATE bills SET due_date = issue_date + 30 WHERE team_id = team AND due_date IS NULL;
            INSERT INTO bill_attachments
                (id, team_id, bill_id, storage_key, filename, content_type, uploaded_at)
            SELECT gen_random_uuid(), team_id, id, pdf_storage_key,
                CASE
                    WHEN lower(pdf_storage_key) LIKE '%.png' THEN bill_number || '.png'
                    WHEN lower(pdf_storage_key) ~ '\\.jpe?g$' THEN bill_number || '.jpg'
                    ELSE bill_number || '.pdf'
                END,
                CASE
                    WHEN lower(pdf_storage_key) LIKE '%.png' THEN 'image/png'
                    WHEN lower(pdf_storage_key) ~ '\\.jpe?g$' THEN 'image/jpeg'
                    ELSE 'application/pdf'
                END,
                created_at
            FROM bills
            WHERE team_id = team
                AND pdf_storage_key IS NOT NULL AND btrim(pdf_storage_key) <> '';
        END LOOP;
        PERFORM set_config('app.tenant_id', '', true);
    END $$""")


def downgrade() -> None:
    op.drop_table("bill_attachments")
    op.execute("ALTER TABLE bills DROP CONSTRAINT IF EXISTS uq_bills_team_id_id")
    op.drop_column("bills", "notes")
    op.drop_column("bills", "archived_by_id")
    op.drop_column("bills", "archived_at")
    op.drop_constraint("ck_bills_approval_status", "bills", type_="check")
    op.drop_column("bills", "approval_status")
    op.drop_column("bills", "due_date")
