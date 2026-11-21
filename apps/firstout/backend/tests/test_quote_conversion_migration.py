"""105_quote_conversion is additive and reversible, and admits the converted status."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db


async def test_quote_conversion_columns_and_status(second_postgres_url):
    url = second_postgres_url
    migrate(url, "104_sales_staff_commission")
    migrate(url, "105_quote_conversion")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            columns = (
                await conn.execute(
                    sa.text("""SELECT table_name, column_name FROM information_schema.columns
                        WHERE column_name IN ('valid_until', 'internal_note',
                            'converted_invoice_id', 'quote_id')
                        AND table_name IN ('quotes', 'till_baskets', 'held_sales')""")
                )
            ).all()
            assert sorted(columns) == [
                ("held_sales", "quote_id"),
                ("quotes", "converted_invoice_id"),
                ("quotes", "internal_note"),
                ("quotes", "valid_until"),
                ("till_baskets", "quote_id"),
            ]
            check = await conn.scalar(
                sa.text("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                    WHERE conname = 'ck_quotes_status'""")
            )
            assert "'converted'" in check
            converted_fk = await conn.scalar(
                sa.text("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                    WHERE conname = 'fk_quotes_converted_invoice_tenant'""")
            )
            assert converted_fk.startswith(
                "FOREIGN KEY (team_id, converted_invoice_id) REFERENCES tax_invoices(team_id, id)"
            )
    finally:
        await engine.dispose()
    migrate(url, "104_sales_staff_commission", command="downgrade")
    migrate(url, "105_quote_conversion")
