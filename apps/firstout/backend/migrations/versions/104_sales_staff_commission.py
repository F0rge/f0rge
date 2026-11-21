"""Sales staff, the colleague on each sale, and the commission exclusion flag.

Revision ID: 104_sales_staff_commission
Revises: 103_invoice_notes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "104_sales_staff_commission"
down_revision = "103_invoice_notes"
branch_labels = None
depends_on = None

_TENANT_VALUE = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
# Documents point at a colleague of their own organisation; a plain FK ignores RLS.
_DOCUMENTS = ("tax_invoices", "quotes")
# Open sales keep the chosen colleague like their customer: unchecked until the sale.
_CARTS = ("till_baskets", "held_sales")
# Books history records a change of an invoice's sales colleague as "updated".
_ACTIONS = "'created', 'posted', 'voided'"


def upgrade() -> None:
    op.create_table(
        "sales_staff",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text(_TENANT_VALUE),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("short_name", sa.String(32)),
        sa.Column("commission_rate", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # Naive UTC, like every TimestampMixin table.
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("team_id", "id", name="uq_sales_staff_team_id_id"),
        sa.CheckConstraint(
            "commission_rate >= 0 AND commission_rate <= 100", name="ck_sales_staff_rate"
        ),
    )
    op.create_index("ix_sales_staff_team_id", "sales_staff", ["team_id"])
    predicate = f"team_id = {_TENANT_VALUE}"
    op.execute(
        f"CREATE POLICY organisation_isolation ON sales_staff FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                   AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE sales_staff ENABLE ROW LEVEL SECURITY;
            ALTER TABLE sales_staff FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")

    for table in _DOCUMENTS:
        op.add_column(table, sa.Column("sales_staff_id", UUID(as_uuid=True)))
        op.create_foreign_key(
            f"fk_{table}_sales_staff_tenant",
            table,
            "sales_staff",
            ["team_id", "sales_staff_id"],
            ["team_id", "id"],
            ondelete="RESTRICT",
        )
        op.create_index(f"ix_{table}_sales_staff", table, ["team_id", "sales_staff_id"])
    for table in _CARTS:
        op.add_column(table, sa.Column("sales_staff_id", UUID(as_uuid=True)))

    for table in ("skus", "invoice_lines"):
        op.add_column(
            table,
            sa.Column(
                "exclude_from_commission",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    op.drop_constraint("ck_books_events_action", "books_events", type_="check")
    op.create_check_constraint(
        "ck_books_events_action", "books_events", f"action IN ({_ACTIONS}, 'updated')"
    )


def downgrade() -> None:
    # The earlier code cannot read "updated" events; forced RLS needs each team's tenant.
    op.execute("""DO $$
    DECLARE team uuid;
    BEGIN
        FOR team IN SELECT id FROM teams LOOP
            PERFORM set_config('app.tenant_id', team::text, true);
            DELETE FROM books_events WHERE team_id = team AND action = 'updated';
        END LOOP;
        PERFORM set_config('app.tenant_id', '', true);
    END $$""")
    op.drop_constraint("ck_books_events_action", "books_events", type_="check")
    op.create_check_constraint("ck_books_events_action", "books_events", f"action IN ({_ACTIONS})")
    for table in ("skus", "invoice_lines"):
        op.drop_column(table, "exclude_from_commission")
    for table in _CARTS:
        op.drop_column(table, "sales_staff_id")
    for table in _DOCUMENTS:
        op.drop_index(f"ix_{table}_sales_staff", table_name=table)
        op.drop_constraint(f"fk_{table}_sales_staff_tenant", table, type_="foreignkey")
        op.drop_column(table, "sales_staff_id")
    op.drop_table("sales_staff")
