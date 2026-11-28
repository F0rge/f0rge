"""The skus workspace fields behind the Stock on hand page: held, stocked_at, below_reorder_min."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.crud.sku_stock_figures import held_documents_by_sku_id
from app.models.customer import Customer
from app.models.inventory import LocationStock, SkuStock
from app.models.layby import Layby, LaybyLine, LaybyStatus
from app.models.location import Location, LocationType
from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderStatus
from app.models.sku import Sku
from app.models.user import User
from tests.conftest import OWNER_EMAIL, authenticate_as, create_test_staff
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
    # Values are not trimmed (like the material filter); the page sends names from a list.
    assert await ids("eq", " Bedfordview ") == set()
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
    # Absolute ceiling for this dataset (26 SKUs, all candidates): 24 statements, measured on
    # 2026-11-28. About 6 for authentication and tenant context, 2 for the role's permissions,
    # 8 for the SKU list itself, and 8 bulk stock figures (locations, on order x2, held x2,
    # available x2, below reorder min). A query per candidate SKU would add at least 26.
    plain = await count(25)
    assert plain <= 24, statements
    assert await count(1) == plain
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
    full = await count(25, **filtered)
    assert full <= 24, statements
    assert await count(1, **filtered) == full


# Each case is one document on its own SKU: (kind, status, qty, held_qty or hold_stock, held).
HELD_CASES = [
    *[
        ("sales_order", status, 3, held_qty, held_qty if counted else 0)
        for status, counted in [
            (SalesOrderStatus.DRAFT, False),
            (SalesOrderStatus.OPEN, True),
            (SalesOrderStatus.AWAITING_STOCK, True),
            (SalesOrderStatus.INVOICED, False),
            (SalesOrderStatus.CANCELLED, False),
        ]
        for held_qty in (3, 2, 0)  # full, partial, released
    ],
    *[
        ("layby", status, 2, hold_stock, 2 if counted and hold_stock else 0)
        for status, counted in [
            (LaybyStatus.OPEN, True),
            (LaybyStatus.READY, True),
            (LaybyStatus.COMPLETED, False),
            (LaybyStatus.CANCELLED, False),
        ]
        for hold_stock in (True, False)
    ],
]
assert {case[1] for case in HELD_CASES} >= set(SalesOrderStatus) | set(LaybyStatus)


async def test_held_definition_over_every_document_state(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    kramerville = uuid.UUID(await _location_id_by_name(owner_client, "Kramerville"))
    owner = await db.scalar(select(User).where(User.email == OWNER_EMAIL))
    customer = Customer(name="Held states customer")
    db.add(customer)
    await db.flush()
    totals = dict(
        subtotal_ex_vat=Decimal(0),
        vat_amount=Decimal(0),
        total_inc_vat=Decimal(0),
        vat_rate=Decimal("0.15"),
    )
    expected: dict[uuid.UUID, Decimal] = {}
    documents: dict[uuid.UUID, tuple[str, str]] = {}
    for index, (kind, status, qty, hold, held) in enumerate(HELD_CASES):
        ref = f"HELD-STATE-{index:02d}"
        sku = Sku(our_ref=ref, our_barcode=ref, name=ref, design=ref, fabric=ref)
        number = f"{kind}-{status.value}-{hold}-{index}"
        if kind == "sales_order":
            doc = SalesOrder(so_number=number, customer_id=customer.id, status=status, **totals)
        else:
            doc = Layby(
                layby_number=number,
                customer_id=customer.id,
                location_id=kramerville,
                due_date=datetime.date.today(),
                hold_stock=hold,
                status=status,
                created_by_user_id=owner.id,
                **totals,
            )
        db.add_all([sku, doc])
        await db.flush()
        if kind == "sales_order":
            line = SalesOrderLine(
                sales_order_id=doc.id,
                sku_id=sku.id,
                qty=qty,
                held_qty=hold,
                unit_ex_vat=Decimal(1),
                description="x",
            )
        else:
            line = LaybyLine(layby_id=doc.id, sku_id=sku.id, qty=qty, unit_ex_vat=Decimal(1))
        db.add(line)
        await db.flush()
        expected[sku.id] = Decimal(held)
        documents[sku.id] = (kind, number)

    found = await held_documents_by_sku_id(db, list(expected))
    for sku_id, held in expected.items():
        docs = found.get(sku_id, [])
        assert sum((doc.qty for doc in docs), Decimal(0)) == held, documents[sku_id]
        assert [(doc.kind, doc.number) for doc in docs] == ([documents[sku_id]] if held else [])
    # The whole-tenant form agrees with the per-SKU form.
    everything = await held_documents_by_sku_id(db)
    assert {sku_id: everything.get(sku_id, []) for sku_id in expected} == {
        sku_id: found.get(sku_id, []) for sku_id in expected
    }


@pytest.mark.parametrize("lifecycle", ["active", "archived"])
async def test_below_reorder_min_with_archived_and_negative_stock(
    owner_client: AsyncClient, lifecycle: str
) -> None:
    db = owner_client.test_db
    bedfordview = uuid.UUID(await _location_id_by_name(owner_client, "Bedfordview"))
    # Kramerville 5, Bedfordview -3: the reorder list counts 2 on hand, below the minimum of 4,
    # while the row's on_hand shows only the positive location (5).
    negative = await _sku_with_opening(
        owner_client, our_ref="SOH-RN-NEGATIVE", opening_qty=5, reorder_min=4
    )
    db.add(LocationStock(sku_id=uuid.UUID(negative["id"]), location_id=bedfordview, on_hand=-3))
    await db.flush()
    # Archived and below its minimum: off the reorder list, flag still true.
    archived = await _sku_with_opening(
        owner_client, our_ref="SOH-RN-ARCHIVED", opening_qty=1, reorder_min=10
    )
    (await db.get(Sku, uuid.UUID(archived["id"]))).is_archived = True
    await db.flush()

    rows = await query(owner_client, "skus", q="SOH-RN-", lifecycle=lifecycle)
    flags = {row["our_ref"]: (row["on_hand"], row["below_reorder_min"]) for row in rows["items"]}
    reorder = await owner_client.get("/api/v1/reorder")
    listed = {
        row["our_ref"]: row["on_hand"]
        for row in reorder.json()
        if row["our_ref"].startswith("SOH-RN-")
    }
    assert listed == {"SOH-RN-NEGATIVE": 2}
    if lifecycle == "active":
        assert flags == {"SOH-RN-NEGATIVE": ("5", True)}
    else:
        assert flags == {"SOH-RN-ARCHIVED": ("1", True)}
