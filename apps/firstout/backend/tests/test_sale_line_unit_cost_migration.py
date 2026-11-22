"""Layby hold cost and invoice line cost of goods land as nullable columns, no backfill."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db
PREVIOUS = "111_sku_curated_catalogue"
UNIT_COST = "112_sale_line_unit_cost"
COLUMNS = sa.text("""SELECT table_name, is_nullable, column_default, numeric_precision,
    numeric_scale FROM information_schema.columns
    WHERE (table_name, column_name) IN
        (('layby_lines', 'hold_unit_cost_zar'), ('invoice_lines', 'unit_cost_zar'))
    ORDER BY table_name""")


async def test_unit_cost_columns_are_nullable_and_round_trip(second_postgres_url):
    url = second_postgres_url
    migrate(url, PREVIOUS)
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        migrate(url, UNIT_COST)
        async with engine.connect() as conn:
            assert (await conn.execute(COLUMNS)).all() == [
                ("invoice_lines", "YES", None, 18, 4),
                ("layby_lines", "YES", None, 18, 4),
            ]

        migrate(url, PREVIOUS, command="downgrade")
        async with engine.connect() as conn:
            assert (await conn.execute(COLUMNS)).all() == []

        migrate(url, UNIT_COST)
        async with engine.connect() as conn:
            assert len((await conn.execute(COLUMNS)).all()) == 2
    finally:
        await engine.dispose()
