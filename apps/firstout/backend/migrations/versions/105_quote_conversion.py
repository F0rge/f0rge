"""Quotes edited like the till: validity, internal note, and conversion to an invoice.

Revision ID: 105_quote_conversion
Revises: 104_sales_staff_commission
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "105_quote_conversion"
down_revision = "104_sales_staff_commission"
branch_labels = None
depends_on = None

_OLD_STATUSES = "'draft', 'sent', 'accepted', 'expired', 'cancelled'"
# Open sales keep the quote they came from like their customer: unchecked until the sale.
_CARTS = ("till_baskets", "held_sales")


def upgrade() -> None:
    op.add_column("quotes", sa.Column("valid_until", sa.Date()))
    op.add_column("quotes", sa.Column("internal_note", sa.Text()))
    # Set only by the till sale that converts the quote, in that sale's transaction.
    op.add_column("quotes", sa.Column("converted_invoice_id", UUID(as_uuid=True)))
    # 080 gave tax_invoices a (team_id, id) key; create it only where one is missing.
    if not any(
        item["column_names"] == ["team_id", "id"]
        for item in sa.inspect(op.get_bind()).get_unique_constraints("tax_invoices")
    ):
        op.create_unique_constraint("uq_tax_invoices_team_id_id", "tax_invoices", ["team_id", "id"])
    # The invoice must belong to the quote's organisation; a plain FK ignores RLS.
    op.create_foreign_key(
        "fk_quotes_converted_invoice_tenant",
        "quotes",
        "tax_invoices",
        ["team_id", "converted_invoice_id"],
        ["team_id", "id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("ck_quotes_status", "quotes", type_="check")
    op.create_check_constraint(
        "ck_quotes_status", "quotes", f"status IN ({_OLD_STATUSES}, 'converted')"
    )
    for table in _CARTS:
        op.add_column(table, sa.Column("quote_id", UUID(as_uuid=True)))


def downgrade() -> None:
    for table in _CARTS:
        op.drop_column(table, "quote_id")
    op.drop_constraint("ck_quotes_status", "quotes", type_="check")
    op.execute("UPDATE quotes SET status = 'accepted' WHERE status = 'converted'")
    op.create_check_constraint("ck_quotes_status", "quotes", f"status IN ({_OLD_STATUSES})")
    op.drop_constraint("fk_quotes_converted_invoice_tenant", "quotes", type_="foreignkey")
    op.drop_column("quotes", "converted_invoice_id")
    op.execute("ALTER TABLE tax_invoices DROP CONSTRAINT IF EXISTS uq_tax_invoices_team_id_id")
    op.drop_column("quotes", "internal_note")
    op.drop_column("quotes", "valid_until")
