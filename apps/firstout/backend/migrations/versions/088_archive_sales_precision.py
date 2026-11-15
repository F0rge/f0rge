"""Preserve the four-decimal VAT and gross totals in archived sales reports.

Revision ID: 088_archive_sales_precision
Revises: 087_cin7_archive_provenance

Numeric(16,4) keeps the previous twelve-digit integer capacity. Operational
invoice calculations remain explicitly rounded to cents. Downgrade is permitted
only when every affected value can be represented exactly as Numeric(14,2).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from f0rge_db.rls import migration_bypass

revision = "088_archive_sales_precision"
down_revision = "087_cin7_archive_provenance"
branch_labels = None
depends_on = None

AMOUNT_COLUMNS = (
    ("tax_invoices", "vat_amount"),
    ("tax_invoices", "total_inc_vat"),
    ("invoice_lines", "vat_amount"),
    ("invoice_lines", "inc_vat"),
    ("archive_credit_notes", "vat_amount"),
    ("archive_credit_notes", "total_inc_vat"),
    ("archive_credit_note_lines", "vat_amount"),
    ("archive_credit_note_lines", "inc_vat"),
)
AMOUNT_TABLES = tuple(dict.fromkeys(table for table, _column in AMOUNT_COLUMNS))


def upgrade() -> None:
    for table, column in AMOUNT_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(14, 2),
            type_=sa.Numeric(16, 4),
            postgresql_using=f'"{column}"::numeric(16, 4)',
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables_sql = ", ".join(f'"{table}"' for table in sorted(AMOUNT_TABLES))
    # The complete preflight and casts share one transaction and table locks.
    bind.execute(sa.text(f"LOCK TABLE {tables_sql} IN ACCESS EXCLUSIVE MODE"))
    # A different organisation's source precision must not be hidden by FORCE RLS.
    with migration_bypass(bind, AMOUNT_TABLES):
        for table, column in AMOUNT_COLUMNS:
            if bind.scalar(
                sa.text(
                    f'SELECT EXISTS (SELECT 1 FROM "{table}" '
                    f"WHERE \"{column}\"::text IN ('NaN', 'Infinity', '-Infinity') "
                    f'OR "{column}" <> trunc("{column}", 2) '
                    f'OR "{column}" < -999999999999.99 '
                    f'OR "{column}" > 999999999999.99)'
                )
            ):
                raise RuntimeError(
                    "Cannot downgrade 088_archive_sales_precision: "
                    f"{table}.{column} contains non-cent, nonfinite or out-of-range amounts"
                )
    for table, column in reversed(AMOUNT_COLUMNS):
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(16, 4),
            type_=sa.Numeric(14, 2),
            postgresql_using=f'"{column}"::numeric(14, 2)',
        )
