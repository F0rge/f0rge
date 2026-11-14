"""Preserve fractional stock and historical purchase quantities.

Revision ID: 085_fractional_inventory
Revises: 084_party_archives

Downgrade refuses fractional or out-of-range quantities instead of rounding.
Retain the numeric columns when rolling application code back until all values
can be represented exactly as PostgreSQL integers.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from f0rge_db.rls import migration_bypass

revision = "085_fractional_inventory"
down_revision = "084_party_archives"
branch_labels = None
depends_on = None

QUANTITY_COLUMNS = (
    ("sku_stock", "on_order"),
    ("location_stock", "on_hand"),
    ("bin_stock", "on_hand"),
    ("stock_adjustment_lines", "qty_delta"),
    ("stocktake_lines", "expected_qty"),
    ("stocktake_lines", "counted_qty"),
    ("transfer_lines", "qty_dispatched"),
    ("transfer_lines", "qty_received"),
    ("po_lines", "qty"),
    ("bill_lines", "qty"),
)
QUANTITY_TABLES = tuple(dict.fromkeys(table for table, _column in QUANTITY_COLUMNS))


def upgrade() -> None:
    for table, column in QUANTITY_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Integer(),
            type_=sa.Numeric(14, 4),
            postgresql_using=f'"{column}"::numeric(14, 4)',
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Keep the preflight and casts in one transaction with no intervening writes.
    tables_sql = ", ".join(f'"{table}"' for table in sorted(QUANTITY_TABLES))
    bind.execute(sa.text(f"LOCK TABLE {tables_sql} IN ACCESS EXCLUSIVE MODE"))
    # FORCE RLS must not hide another organisation's fractional quantities.
    # The shared helper removes its transient policy on success; Alembic rolls
    # the entire transaction back on failure, including these temporary policies.
    with migration_bypass(bind, QUANTITY_TABLES):
        for table, column in QUANTITY_COLUMNS:
            invalid = bind.scalar(
                sa.text(
                    f'SELECT EXISTS (SELECT 1 FROM "{table}" '
                    f'WHERE "{column}" <> trunc("{column}") '
                    f'OR "{column}" < -2147483648 OR "{column}" > 2147483647)'
                )
            )
            if invalid:
                raise RuntimeError(
                    "Cannot downgrade 085_fractional_inventory: "
                    f"{table}.{column} contains fractional or out-of-range quantities"
                )
    for table, column in reversed(QUANTITY_COLUMNS):
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(14, 4),
            type_=sa.Integer(),
            postgresql_using=f'"{column}"::integer',
        )
