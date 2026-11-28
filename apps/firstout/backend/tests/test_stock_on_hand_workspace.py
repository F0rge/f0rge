"""The skus workspace fields behind the Stock on hand page: held, stocked_at, below_reorder_min."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models.inventory import LocationStock, SkuStock
from app.models.location import Location, LocationType
from app.models.sku import Sku
from tests.conftest import authenticate_as, create_test_staff
from tests.test_purchase_orders import _location_id_by_name
from tests.test_record_workspace import query
from tests.test_reorder import _sku_with_opening
from tests.test_sku_bom import _sku
from tests.test_sku_overview import _documents_holding


async def test_held_matches_the_overview_and_filters_and_sorts(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    kramerville = await _location_id_by_name(owner_client, "Kramerville")
    held = await _sku(
        owner_client,
        "SOH-HELD",
        opening_location_id=kramerville,
        opening_qty=10,
        opening_cost="1.00",
    )
    plain = await _sku(owner_client, "SOH-PLAIN")
    # An open sales order holding 2 and a stock-holding layby of 1 (plus ignored documents).
    await _documents_holding(db, uuid.UUID(held["id"]), uuid.UUID(kramerville))

    overview = (await owner_client.get(f"/api/v1/skus/{held['id']}/overview")).json()["stock"]
    assert [d["kind"] for d in overview["held_documents"]] == ["sales_order", "layby"]
    rows = await query(owner_client, "skus", q="SOH-", sort={"field": "held", "direction": "desc"})
    assert [(row["id"], row["held"]) for row in rows["items"]] == [
        (held["id"], "3"),
        (plain["id"], "0"),
    ]
    assert Decimal(rows["items"][0]["held"]) == Decimal(str(overview["held"]))
    filtered = await query(
        owner_client, "skus", q="SOH-", filters=[{"field": "held", "operator": "gt", "value": 0}]
    )
    assert [row["id"] for row in filtered["items"]] == [held["id"]]


async def test_stocked_at_matches_stock_above_zero_by_location_name(
    owner_client: AsyncClient,
) -> None:
    db = owner_client.test_db
    bedfordview = uuid.UUID(await _location_id_by_name(owner_client, "Bedfordview"))
    kramerville = uuid.UUID(await _location_id_by_name(owner_client, "Kramerville"))
    old = Location(name="SOH Old Store", type=LocationType.WAREHOUSE, is_archived=True)
    db.add(old)
    await db.flush()
    both = await _sku(owner_client, "SOH-AT-BOTH")
    zero = await _sku(owner_client, "SOH-AT-ZERO")
    archived = await _sku(owner_client, "SOH-AT-OLD")
    nowhere = await _sku(owner_client, "SOH-AT-NONE")
    db.add_all(
        [
            LocationStock(sku_id=uuid.UUID(both["id"]), location_id=bedfordview, on_hand=4),
            LocationStock(sku_id=uuid.UUID(both["id"]), location_id=kramerville, on_hand=10),
            # A zero row at Bedfordview is not stock there.
            LocationStock(sku_id=uuid.UUID(zero["id"]), location_id=bedfordview, on_hand=0),
            LocationStock(sku_id=uuid.UUID(zero["id"]), location_id=kramerville, on_hand=1),
            # Stock still sitting at an archived location counts, like the By location column.
            LocationStock(sku_id=uuid.UUID(archived["id"]), location_id=old.id, on_hand=2),
        ]
    )
    await db.flush()

    async def ids(operator: str, value: str) -> set[str]:
        filters = [{"field": "stocked_at", "operator": operator, "value": value}]
        found = await query(owner_client, "skus", q="SOH-AT-", filters=filters)
        return {row["id"] for row in found["items"]}

    assert await ids("eq", "bedfordview") == {both["id"]}
    assert await ids("eq", "Kramerville") == {both["id"], zero["id"]}
    assert await ids("eq", "soh old store") == {archived["id"]}
    assert await ids("ne", "BEDFORDVIEW") == {zero["id"], archived["id"], nowhere["id"]}
    row = (await query(owner_client, "skus", q="SOH-AT-BOTH"))["items"][0]
    assert [loc["location_name"] for loc in row["stock_locations"]] == [
        "Bedfordview",
        "Kramerville",
    ]


async def test_below_reorder_min_is_the_reorder_lists_condition(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    below = await _sku_with_opening(
        owner_client, our_ref="SOH-RO-BELOW", opening_qty=3, reorder_min=10
    )
    covered = await _sku_with_opening(
        owner_client, our_ref="SOH-RO-COVERED", opening_qty=3, reorder_min=10
    )
    db.add(SkuStock(sku_id=uuid.UUID(covered["id"]), on_order=Decimal(7)))  # 3 + 7 is not below 10
    await db.flush()
    await _sku_with_opening(owner_client, our_ref="SOH-RO-AT", opening_qty=10, reorder_min=10)
    await _sku_with_opening(owner_client, our_ref="SOH-RO-NOMIN", opening_qty=1)

    async def flagged() -> set[str]:
        rows = await query(
            owner_client,
            "skus",
            q="SOH-RO-",
            filters=[{"field": "below_reorder_min", "operator": "eq", "value": True}],
        )
        assert all(row["below_reorder_min"] for row in rows["items"])
        return {row["id"] for row in rows["items"]}

    async def reorder_list() -> set[str]:
        response = await owner_client.get("/api/v1/reorder")
        assert response.status_code == 200, response.text
        return {row["sku_id"] for row in response.json() if row["our_ref"].startswith("SOH-RO-")}

    # No SKU is do-not-reorder: the flag and the reorder list pick the same SKUs.
    assert await flagged() == await reorder_list() == {below["id"]}
    on_order = await query(owner_client, "skus", q="SOH-RO-COVERED")
    assert (on_order["items"][0]["on_order"], on_order["items"][0]["below_reorder_min"]) == (
        "7",
        False,
    )

    # Do not reorder takes the SKU off the reorder list; the flag still describes its stock.
    sku = await db.get(Sku, uuid.UUID(below["id"]))
    sku.do_not_reorder = True
    await db.flush()
    assert await reorder_list() == set()
    assert await flagged() == {below["id"]}


async def test_page_of_25_issues_no_per_row_queries(
    owner_client: AsyncClient, async_engine: AsyncEngine
) -> None:
    kramerville = await _location_id_by_name(owner_client, "Kramerville")
    for index in range(26):
        await _sku(
            owner_client,
            f"SOH-COUNT-{index:02d}",
            opening_location_id=kramerville,
            opening_qty=1,
            opening_cost="1.00",
        )
    await create_test_staff(owner_client, email="soh-count-warehouse@example.com", role="warehouse")
    await authenticate_as(owner_client, "soh-count-warehouse@example.com")
    statements: list[str] = []

    def capture(_conn, _cursor, statement, *_args) -> None:
        statements.append(statement)

    async def count(limit: int, **body) -> int:
        statements.clear()
        event.listen(async_engine.sync_engine, "before_cursor_execute", capture)
        try:
            result = await query(owner_client, "skus", q="SOH-COUNT-", limit=limit, **body)
        finally:
            event.remove(async_engine.sync_engine, "before_cursor_execute", capture)
        assert len(result["items"]) == limit
        # A staff member without stock.cost.view still sees no cost on any row.
        assert all(row["average_unit_cost_zar"] is None for row in result["items"])
        return len(statements)

    # Plain page: figures fetched for the page in bulk.
    assert await count(1) == await count(25)
    # Every new field used to filter and sort: fetched once for all rows.
    filtered = {
        "filters": [
            {"field": "stocked_at", "operator": "eq", "value": "kramerville"},
            {"field": "held", "operator": "gte", "value": 0},
            {"field": "below_reorder_min", "operator": "eq", "value": False},
            {"field": "on_order", "operator": "gte", "value": 0},
        ],
        "sort": {"field": "held"},
    }
    assert await count(1, **filtered) == await count(25, **filtered)
