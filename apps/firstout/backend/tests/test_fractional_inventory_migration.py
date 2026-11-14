"""Real Alembic chains preserve records and refuse lossy quantity rollback."""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.no_db
BACKEND = Path(__file__).resolve().parents[1]
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


def migrate(
    url, revision, *, command="upgrade", success=True, error="fractional or out-of-range quantities"
):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url, "MIGRATION_DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    if success:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0 and error in result.stderr


async def seed_old_records(engine):
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    async with engine.begin() as conn:

        async def insert(table, *, timestamps=True, **fields):
            fields.setdefault("id", uuid.uuid4())
            if timestamps:
                fields.update(created_at=now, updated_at=now)
            names = ",".join(fields)
            parameters = ",".join(":" + name for name in fields)
            await conn.execute(
                sa.text(f"INSERT INTO {table} ({names}) VALUES ({parameters})"), fields
            )
            return fields["id"]

        team_id = await insert(
            "teams", name="Quantity migration", slug="quantity-migration", status="active"
        )
        supplier_id = await insert(
            "suppliers", team_id=team_id, name="Quantity supplier", default_currency="ZAR"
        )
        location_id = await insert(
            "locations",
            team_id=team_id,
            name="Quantity warehouse",
            type="warehouse",
            is_archived=False,
        )
        sku_id = await insert(
            "skus",
            team_id=team_id,
            our_ref="QUANTITY-MIGRATION",
            our_barcode="QUANTITY-MIGRATION",
            name="Quantity item",
            design="Quantity design",
            fabric="Quantity fabric",
            storefront_published=False,
        )
        stock_id = await insert(
            "location_stock",
            team_id=team_id,
            sku_id=sku_id,
            location_id=location_id,
            on_hand=2,
            unit_cost_zar=Decimal("100"),
        )
        bill_id = await insert(
            "bills",
            team_id=team_id,
            bill_number="QUANTITY-BILL",
            supplier_id=supplier_id,
            supplier_ref="QUANTITY-BILL",
            issue_date=datetime.date.today(),
            currency="ZAR",
            fx_to_zar=Decimal(1),
            amount_foreign=Decimal(100),
            amount_zar=Decimal(100),
            amount_paid_zar=Decimal(0),
            amount_paid_foreign=Decimal(0),
        )
        line_id = await insert(
            "bill_lines",
            timestamps=False,
            team_id=team_id,
            bill_id=bill_id,
            description="Quantity history",
            qty=2,
            unit_amount=Decimal(50),
            amount_foreign=Decimal(100),
            sort_order=0,
        )
    return team_id, sku_id, stock_id, line_id


async def column_shapes(conn):
    result = {}
    for table, column in QUANTITY_COLUMNS:
        result[(table, column)] = (
            await conn.execute(
                sa.text(
                    "SELECT data_type,numeric_precision,numeric_scale,is_nullable FROM information_schema.columns WHERE table_name=:table AND column_name=:column"
                ),
                {"table": table, "column": column},
            )
        ).one()
    return result


async def test_085_upgrade_exact_quantity_and_whole_downgrade_round_trip(second_postgres_url):
    url = second_postgres_url
    migrate(url, "084_party_archives")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        team_id, sku_id, stock_id, line_id = await seed_old_records(engine)
        async with engine.connect() as conn:
            before = await column_shapes(conn)
        migrate(url, "085_fractional_inventory")
        async with engine.begin() as conn:
            shapes = await column_shapes(conn)
            assert all(row[:3] == ("numeric", 14, 4) for row in shapes.values())
            assert all(row.is_nullable == before[key].is_nullable for key, row in shapes.items())
            assert await conn.scalar(
                sa.text("SELECT on_hand FROM location_stock WHERE id=:id"), {"id": stock_id}
            ) == Decimal(2)
            await conn.execute(
                sa.text("UPDATE location_stock SET on_hand=0.25 WHERE id=:id"), {"id": stock_id}
            )
            await conn.execute(
                sa.text("UPDATE bill_lines SET qty=4.576 WHERE id=:id"), {"id": line_id}
            )
        async with engine.connect() as conn:
            assert await conn.scalar(
                sa.text("SELECT qty FROM bill_lines WHERE id=:id"), {"id": line_id}
            ) == Decimal("4.5760")
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("UPDATE location_stock SET on_hand=2 WHERE id=:id"), {"id": stock_id}
            )
            await conn.execute(
                sa.text("UPDATE bill_lines SET qty=-2147483648 WHERE id=:id"), {"id": line_id}
            )
        migrate(url, "084_party_archives", command="downgrade")
        async with engine.connect() as conn:
            assert all(row.data_type == "integer" for row in (await column_shapes(conn)).values())
            assert (
                await conn.scalar(
                    sa.text("SELECT count(*) FROM skus WHERE id=:id AND team_id=:team"),
                    {"id": sku_id, "team": team_id},
                )
                == 1
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT qty FROM bill_lines WHERE id=:id"), {"id": line_id}
                )
                == -2147483648
            )
        migrate(url, "085_fractional_inventory")
    finally:
        await engine.dispose()


@pytest.mark.parametrize("invalid", ["0.125", "2147483648", "NaN"])
async def test_085_lossy_downgrade_refused_without_partial_schema_change(
    second_postgres_url, invalid
):
    url = second_postgres_url
    migrate(url, "084_party_archives")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        _team, _sku, stock_id, line_id = await seed_old_records(engine)
        migrate(url, "085_fractional_inventory")
        async with engine.begin() as conn:
            # Last column checked: an early cast before this check would corrupt earlier fields.
            await conn.execute(
                sa.text("UPDATE bill_lines SET qty=CAST(:qty AS numeric) WHERE id=:id"),
                {"qty": invalid, "id": line_id},
            )
        migrate(url, "084_party_archives", command="downgrade", success=False)
        async with engine.connect() as conn:
            assert all(
                row[:3] == ("numeric", 14, 4) for row in (await column_shapes(conn)).values()
            )
            assert (
                await conn.scalar(sa.text("SELECT version_num FROM alembic_version"))
                == "085_fractional_inventory"
            )
            assert await conn.scalar(
                sa.text("SELECT on_hand FROM location_stock WHERE id=:id"), {"id": stock_id}
            ) == Decimal(2)
            preserved = await conn.scalar(
                sa.text("SELECT qty FROM bill_lines WHERE id=:id"), {"id": line_id}
            )
            assert str(preserved) == "NaN" if invalid == "NaN" else preserved == Decimal(invalid)
    finally:
        await engine.dispose()


async def test_086_sellability_defaults_preserve_existing_stock_and_history(second_postgres_url):
    url = second_postgres_url
    migrate(url, "085_fractional_inventory")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        _team, sku_id, stock_id, line_id = await seed_old_records(engine)
        migrate(url, "086_cin7_sellability")
        async with engine.begin() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT is_sellable FROM skus WHERE id=:id"), {"id": sku_id}
                )
                is True
            )
            await conn.execute(
                sa.text("UPDATE skus SET is_sellable=false WHERE id=:id"), {"id": sku_id}
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT is_sellable FROM skus WHERE id=:id"), {"id": sku_id}
                )
                is False
            )
            assert await conn.scalar(
                sa.text("SELECT on_hand FROM location_stock WHERE id=:id"), {"id": stock_id}
            ) == Decimal(2)
            assert await conn.scalar(
                sa.text("SELECT qty FROM bill_lines WHERE id=:id"), {"id": line_id}
            ) == Decimal(2)
        migrate(url, "085_fractional_inventory", command="downgrade")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(sa.text("SELECT count(*) FROM skus WHERE id=:id"), {"id": sku_id})
                == 1
            )
            assert (
                await conn.scalar(
                    sa.text(
                        "SELECT count(*) FROM information_schema.columns WHERE table_name='skus' AND column_name='is_sellable'"
                    )
                )
                == 0
            )
    finally:
        await engine.dispose()


async def test_087_provenance_and_duplicate_archive_refs_survive_refused_downgrade(
    second_postgres_url,
):
    url = second_postgres_url
    migrate(url, "086_cin7_sellability")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        team, sku, _stock, line_id = await seed_old_records(engine)
        migrate(url, "087_cin7_archive_provenance")
        async with engine.begin() as conn:
            bill_id = await conn.scalar(
                sa.text("SELECT bill_id FROM bill_lines WHERE id=:id"), {"id": line_id}
            )
            assert await conn.scalar(
                sa.text("SELECT cin7_source_payload IS NULL FROM bills WHERE id=:id"),
                {"id": bill_id},
            )
            await conn.execute(
                sa.text(
                    "UPDATE bills SET cin7_source_payload=CAST(:payload AS jsonb) WHERE id=:id"
                ),
                {
                    "id": bill_id,
                    "payload": '{"rows":[{"Quantity":"4.576","Cost":"-1.2300","Tax":"15.00"}]}',
                },
            )
        migrate(
            url,
            "086_cin7_sellability",
            command="downgrade",
            success=False,
            error="retains Cin7 source payloads",
        )
        async with engine.begin() as conn:
            assert (
                await conn.scalar(
                    sa.text(
                        "SELECT cin7_source_payload->'rows'->0->>'Cost' FROM bills WHERE id=:id"
                    ),
                    {"id": bill_id},
                )
                == "-1.2300"
            )
            assert (
                await conn.scalar(sa.text("SELECT version_num FROM alembic_version"))
                == "087_cin7_archive_provenance"
            )
            await conn.execute(
                sa.text("UPDATE bills SET cin7_source_payload=NULL WHERE id=:id"), {"id": bill_id}
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO bills (id,team_id,bill_number,supplier_id,supplier_ref,issue_date,currency,fx_to_zar,amount_foreign,amount_zar,amount_paid_zar,amount_paid_foreign,is_archive,created_at,updated_at) SELECT :new_id,team_id,'CIN7-ARCHIVE-DUPLICATE',supplier_id,supplier_ref,issue_date,currency,fx_to_zar,amount_foreign,amount_zar,amount_paid_zar,amount_paid_foreign,true,created_at,updated_at FROM bills WHERE id=:id"
                ),
                {"new_id": uuid.uuid4(), "id": bill_id},
            )
        # The archive reference is accepted while a conflicting live reference remains forbidden.
        with pytest.raises(sa.exc.IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text(
                        "UPDATE bills SET is_archive=false WHERE bill_number='CIN7-ARCHIVE-DUPLICATE'"
                    )
                )
        migrate(
            url,
            "086_cin7_sellability",
            command="downgrade",
            success=False,
            error="retained supplier references conflict",
        )
        async with engine.begin() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT count(*) FROM bills WHERE team_id=:id"), {"id": team}
                )
                == 2
            )
            await conn.execute(
                sa.text("DELETE FROM bills WHERE bill_number='CIN7-ARCHIVE-DUPLICATE'")
            )
            po_id = uuid.uuid4()
            await conn.execute(
                sa.text(
                    "INSERT INTO purchase_orders (id,team_id,po_number,supplier_id,status,is_archive,created_at,updated_at) SELECT :po,team_id,'NULL-PRICE-ARCHIVE',supplier_id,'open',true,created_at,updated_at FROM bills WHERE id=:bill"
                ),
                {"po": po_id, "bill": bill_id},
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO po_lines (id,team_id,po_id,sku_id,qty,factory_unit_amount,created_at,updated_at) VALUES (:id,:team,:po,:sku,4.576,NULL,now(),now())"
                ),
                {"id": uuid.uuid4(), "team": team, "po": po_id, "sku": sku},
            )
        migrate(
            url,
            "086_cin7_sellability",
            command="downgrade",
            success=False,
            error="retain unknown factory unit amounts",
        )
        async with engine.begin() as conn:
            assert await conn.scalar(
                sa.text("SELECT factory_unit_amount IS NULL FROM po_lines WHERE po_id=:id"),
                {"id": po_id},
            )
            assert (
                await conn.scalar(
                    sa.text(
                        "SELECT is_nullable FROM information_schema.columns WHERE table_name='po_lines' AND column_name='factory_unit_amount'"
                    )
                )
                == "YES"
            )
            await conn.execute(sa.text("DELETE FROM purchase_orders WHERE id=:id"), {"id": po_id})
        migrate(url, "086_cin7_sellability", command="downgrade")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text(
                        "SELECT count(*) FROM information_schema.columns WHERE column_name='cin7_source_payload'"
                    )
                )
                == 0
            )
            assert await conn.scalar(
                sa.text("SELECT qty FROM bill_lines WHERE id=:id"), {"id": line_id}
            ) == Decimal(2)
    finally:
        await engine.dispose()
