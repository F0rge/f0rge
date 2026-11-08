"""Inventory list loads stock in bulk instead of once per SKU."""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState

from app.config import settings
from app.crud.user import UserCRUD
from app.models.inventory import LocationStock, SkuStock
from app.models.location import Location
from app.models.location_bin import BinStock, LocationBin
from app.models.sku import Sku
from app.services.inventory import InventoryService

SKU_COUNT = 25


def _table_hits(statements: list[str], table: str) -> int:
    needle = table.lower()
    return sum(1 for statement in statements if needle in statement.lower())


async def _seed_stock(db: AsyncSession) -> list[uuid.UUID]:
    locations = list((await db.execute(select(Location))).scalars().all())
    bins = list(
        (await db.execute(select(LocationBin).where(LocationBin.is_default.is_(True))))
        .scalars()
        .all()
    )
    bin_by_location = {row.location_id: row for row in bins}
    sku_ids: list[uuid.UUID] = []
    for index in range(SKU_COUNT):
        sku = Sku(
            our_ref=f"BULK-{index:03d}",
            our_barcode=f"BULK-BAR-{index:03d}",
            name=f"Bulk sofa {index}",
            design=f"Bulk design {index}",
            fabric="Linen",
            category="Sofas" if index % 2 == 0 else "Dining",
        )
        db.add(sku)
        await db.flush()
        sku_ids.append(sku.id)
        db.add(SkuStock(sku_id=sku.id, on_order=index % 3))
        for location in locations:
            cost = Decimal("10.00") if location.name == "Kramerville" else Decimal("30.00")
            db.add(
                LocationStock(
                    sku_id=sku.id,
                    location_id=location.id,
                    on_hand=2,
                    unit_cost_zar=cost,
                )
            )
            floor = bin_by_location[location.id]
            db.add(BinStock(sku_id=sku.id, bin_id=floor.id, on_hand=2))
    await db.flush()
    return sku_ids


def _listen(statements: list[str]):
    def before(orm_execute_state: ORMExecuteState) -> None:
        statements.append(str(orm_execute_state.statement))

    return before


async def test_inventory_list_is_three_stock_queries(async_db: AsyncSession) -> None:
    sku_ids = await _seed_stock(async_db)
    owner = await UserCRUD(async_db).get_by_email(settings.seed_owner_email)
    assert owner is not None
    owner_id = owner.id
    service = InventoryService(async_db)

    async_db.sync_session.expire_all()
    new_statements: list[str] = []
    listener = _listen(new_statements)
    event.listen(async_db.sync_session, "do_orm_execute", listener)
    started = time.perf_counter()
    rows = await service.list(owner_id)
    new_elapsed = time.perf_counter() - started
    event.remove(async_db.sync_session, "do_orm_execute", listener)

    bulk = [row for row in rows if row.our_ref.startswith("BULK-")]
    assert len(bulk) == SKU_COUNT
    sample = next(row for row in bulk if row.our_ref == "BULK-001")
    assert sample.on_hand == 4
    assert sample.on_order == 1
    assert sample.sellable is True
    assert sample.unit_cost_zar == Decimal("20")
    assert {location.location_name for location in sample.locations} == {
        "Kramerville",
        "Bedfordview",
    }
    assert all(
        len(location.bins) == 1 and location.bins[0].on_hand == 2 for location in sample.locations
    )
    assert _table_hits(new_statements, "sku_stock") == 1
    assert _table_hits(new_statements, "location_stock") == 1
    assert _table_hits(new_statements, "bin_stock") == 1
    assert new_elapsed < 1

    async_db.sync_session.expire_all()
    legacy_statements: list[str] = []
    legacy_listener = _listen(legacy_statements)
    event.listen(async_db.sync_session, "do_orm_execute", legacy_listener)
    started = time.perf_counter()
    for sku_id in sku_ids:
        await service.sku_stock_crud.get_by_sku_id(sku_id)
        await service.location_stock_crud.list_by_sku_id(sku_id)
        await service.bin_stock_crud.list_nonzero_for_skus([sku_id])
    legacy_elapsed = time.perf_counter() - started
    event.remove(async_db.sync_session, "do_orm_execute", legacy_listener)

    assert _table_hits(legacy_statements, "sku_stock") == SKU_COUNT
    assert _table_hits(legacy_statements, "location_stock") == SKU_COUNT
    assert _table_hits(legacy_statements, "bin_stock") == SKU_COUNT
    print(
        "INVENTORY_BENCH "
        f"skus={SKU_COUNT} "
        f"new_stock_queries=3 new_s={new_elapsed:.4f} "
        f"legacy_stock_queries={SKU_COUNT * 3} legacy_s={legacy_elapsed:.4f}"
    )
