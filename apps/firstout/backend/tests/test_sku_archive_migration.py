"""SKU archive migration preserves exact stock, recipes and historical identity."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate, seed_old_records

pytestmark = pytest.mark.no_db
PREVIOUS = "090_release_migration_receipts"
ARCHIVE = "091_sku_archive"


async def test_sku_archive_migration_preserves_records_defaults_and_round_trip(second_postgres_url):
    url = second_postgres_url
    migrate(url, PREVIOUS)
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        team_id, sku_id, stock_id, bill_line_id = await seed_old_records(engine)
        component_id, recipe_id = uuid.uuid4(), uuid.uuid4()
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("UPDATE location_stock SET on_hand=0.1250 WHERE id=:id"),
                {"id": stock_id},
            )
            await conn.execute(
                sa.text("""INSERT INTO skus
                    (id,team_id,our_ref,our_barcode,name,design,fabric,created_at,updated_at)
                    VALUES (:id,:team,'ARCHIVE-COMP','ARCHIVE-COMP','Component',
                            'Archive component','None',now(),now())"""),
                {"id": component_id, "team": team_id},
            )
            await conn.execute(
                sa.text("""INSERT INTO sku_bom_lines
                    (id,team_id,parent_sku_id,component_sku_id,qty,created_at,updated_at)
                    VALUES (:id,:team,:parent,:component,0.5000,now(),now())"""),
                {"id": recipe_id, "team": team_id, "parent": sku_id, "component": component_id},
            )
        migrate(url, ARCHIVE)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    sa.text("""SELECT id,team_id,our_ref,our_barcode,is_archived,
                               archived_at,archived_by_id FROM skus WHERE id=:id"""),
                    {"id": sku_id},
                )
            ).one()
            assert row.id == sku_id and row.team_id == team_id
            assert row.our_ref == row.our_barcode == "QUANTITY-MIGRATION"
            assert row.is_archived is False
            assert row.archived_at is None and row.archived_by_id is None
            assert (
                await conn.scalar(
                    sa.text("""SELECT data_type FROM information_schema.columns
                    WHERE table_name='skus' AND column_name='archived_at'""")
                )
                == "timestamp without time zone"
            )
            assert await conn.scalar(
                sa.text("SELECT on_hand FROM location_stock WHERE id=:id"), {"id": stock_id}
            ) == Decimal("0.1250")
            assert await conn.scalar(
                sa.text("SELECT qty FROM sku_bom_lines WHERE id=:id"), {"id": recipe_id}
            ) == Decimal("0.5000")
            assert await conn.scalar(
                sa.text("SELECT qty FROM bill_lines WHERE id=:id"), {"id": bill_line_id}
            ) == Decimal("2")
            assert "(team_id, is_archived)" in await conn.scalar(
                sa.text(
                    "SELECT indexdef FROM pg_indexes WHERE indexname='ix_skus_team_id_is_archived'"
                )
            )
            inserted = await conn.scalar(
                sa.text("""INSERT INTO skus
                    (id,team_id,our_ref,our_barcode,name,design,fabric,created_at,updated_at)
                    VALUES (:id,:team,'ARCHIVE-NEW','ARCHIVE-NEW','New SKU',
                            'Archive new','None',now(),now()) RETURNING is_archived"""),
                {"id": uuid.uuid4(), "team": team_id},
            )
            assert inserted is False
            await conn.execute(
                sa.text("UPDATE skus SET is_archived=true,archived_at=now() WHERE id=:id"),
                {"id": sku_id},
            )
        migrate(url, PREVIOUS, command="downgrade")
        async with engine.connect() as conn:
            assert await conn.scalar(
                sa.text("SELECT on_hand FROM location_stock WHERE id=:id"), {"id": stock_id}
            ) == Decimal("0.1250")
            assert await conn.scalar(
                sa.text("SELECT qty FROM sku_bom_lines WHERE id=:id"), {"id": recipe_id}
            ) == Decimal("0.5000")
            assert (
                await conn.scalar(
                    sa.text("SELECT count(*) FROM skus WHERE team_id=:team"), {"team": team_id}
                )
                == 3
            )
        migrate(url, ARCHIVE)
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT is_archived FROM skus WHERE id=:id"), {"id": sku_id}
                )
                is False
            )
    finally:
        await engine.dispose()
