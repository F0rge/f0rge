"""sku_id indexes are created only when a leading sku_id index is missing."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine


def _import_migration():
    import importlib

    return importlib.import_module("migrations.versions.066_stock_sku_indexes")


async def test_existing_stock_tables_already_index_sku_id(async_engine: AsyncEngine) -> None:
    migration = _import_migration()

    def check(connection: sa.Connection) -> None:
        for table in ("sku_stock", "location_stock", "bin_stock"):
            assert migration.has_leading_sku_id_index(connection, table)
            before = [index["name"] for index in sa.inspect(connection).get_indexes(table)]
            migration.ensure_sku_id_index(connection, table, f"ix_{table}_sku_id_extra")
            after = [index["name"] for index in sa.inspect(connection).get_indexes(table)]
            assert before == after

    async with async_engine.connect() as conn:
        await conn.run_sync(check)


async def test_ensure_sku_id_index_creates_and_is_idempotent(async_engine: AsyncEngine) -> None:
    migration = _import_migration()

    def check(connection: sa.Connection) -> None:
        connection.execute(
            sa.text("CREATE TABLE sku_index_probe (id uuid PRIMARY KEY, sku_id uuid NOT NULL)")
        )
        assert not migration.has_leading_sku_id_index(connection, "sku_index_probe")
        migration.ensure_sku_id_index(connection, "sku_index_probe", "ix_sku_index_probe_sku_id")
        migration.ensure_sku_id_index(connection, "sku_index_probe", "ix_sku_index_probe_sku_id")
        indexes = sa.inspect(connection).get_indexes("sku_index_probe")
        assert [index["name"] for index in indexes] == ["ix_sku_index_probe_sku_id"]
        assert indexes[0]["column_names"] == ["sku_id"]
        connection.execute(sa.text("DROP TABLE sku_index_probe"))

    async with async_engine.begin() as conn:
        await conn.run_sync(check)
