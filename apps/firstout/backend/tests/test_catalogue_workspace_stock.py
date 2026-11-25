from __future__ import annotations

import uuid
from decimal import Decimal

from app.crud.purchase_order import LocationStockCRUD, SkuStockCRUD
from app.models.inventory import LocationStock, SkuStock
from app.models.location import Location, LocationType
from app.models.sku import Sku
from app.models.team import Team
from tests.conftest import authenticate_as, create_test_staff
from tests.test_purchase_orders import _location_id_by_name
from tests.test_record_workspace import execute, prepare, query
from tests.test_sku_bom import _sku


async def test_catalogue_stock_totals_filters_and_numeric_sort_before_pagination(
    owner_client, async_db
):
    empty = await _sku(owner_client, "WORKSPACE-STOCK-EMPTY")
    fractional = await _sku(owner_client, "WORKSPACE-STOCK-FRACTIONAL")
    large = await _sku(owner_client, "WORKSPACE-STOCK-LARGE")
    bedfordview = await _location_id_by_name(owner_client, "Bedfordview")
    kramerville = await _location_id_by_name(owner_client, "Kramerville")
    async_db.add_all(
        [
            LocationStock(
                sku_id=uuid.UUID(fractional["id"]),
                location_id=uuid.UUID(bedfordview),
                on_hand=Decimal("1.1250"),
                unit_cost_zar=Decimal("12.50"),
            ),
            LocationStock(
                sku_id=uuid.UUID(fractional["id"]),
                location_id=uuid.UUID(kramerville),
                on_hand=Decimal("0.8751"),
            ),
            LocationStock(
                sku_id=uuid.UUID(large["id"]), location_id=uuid.UUID(bedfordview), on_hand=11
            ),
            SkuStock(sku_id=uuid.UUID(fractional["id"]), on_order=Decimal("3.5000")),
        ]
    )
    await async_db.flush()
    await create_test_staff(
        owner_client, email="catalogue-stock-warehouse@example.com", role="warehouse"
    )
    await authenticate_as(owner_client, "catalogue-stock-warehouse@example.com")

    search = {"q": "WORKSPACE-STOCK", "sort": {"field": "on_hand"}, "limit": 1}
    first = await query(owner_client, "skus", **search)
    assert first["total"] == 3
    zero = first["items"][0]
    assert (zero["id"], zero["on_hand"], zero["on_order"], zero["stock_locations"]) == (
        empty["id"],
        "0",
        "0",
        [],
    )

    next_row = (await query(owner_client, "skus", **search, offset=1))["items"][0]
    assert (next_row["id"], next_row["on_hand"], next_row["on_order"]) == (
        fractional["id"],
        "2.0001",
        "3.5",
    )
    assert next_row["average_unit_cost_zar"] is None
    assert next_row["stock_locations"] == [
        {"location_id": bedfordview, "location_name": "Bedfordview", "on_hand": "1.125"},
        {"location_id": kramerville, "location_name": "Kramerville", "on_hand": "0.8751"},
    ]
    descending = await query(
        owner_client,
        "skus",
        q=search["q"],
        sort={"field": "on_hand", "direction": "desc"},
        filters=[{"field": "is_sellable", "operator": "eq", "value": True}],
        limit=2,
    )
    assert [row["id"] for row in descending["items"]] == [large["id"], fractional["id"]]
    assert [row["on_hand"] for row in descending["items"]] == ["11", "2.0001"]
    ordinary = await query(owner_client, "skus", q="WORKSPACE-STOCK-FRACTIONAL")
    assert ordinary["items"] == [next_row]
    stock_filtered = await query(
        owner_client,
        "skus",
        q=search["q"],
        filters=[{"field": "on_hand", "operator": "gte", "value": "2.0001"}],
    )
    assert {row["id"] for row in stock_filtered["items"]} == {fractional["id"], large["id"]}


async def test_catalogue_stock_scope_and_bulk_revisions(owner_client, async_db):
    own = await _sku(owner_client, "WORKSPACE-STOCK-SCOPE-OWN")
    other = Team(name="Catalogue stock other organisation", slug="catalogue-stock-other-org")
    async_db.add(other)
    await async_db.flush()
    foreign_sku = Sku(
        team_id=other.id,
        our_ref="WORKSPACE-STOCK-SCOPE-FOREIGN",
        our_barcode="WORKSPACE-STOCK-SCOPE-FOREIGN",
        name="Foreign catalogue SKU",
        design="Foreign design",
        fabric="Foreign fabric",
    )
    foreign_location = Location(
        team_id=other.id, name="Foreign warehouse", type=LocationType.WAREHOUSE
    )
    async_db.add_all([foreign_sku, foreign_location])
    await async_db.flush()
    async_db.add_all(
        [
            LocationStock(
                team_id=other.id, sku_id=foreign_sku.id, location_id=foreign_location.id, on_hand=88
            ),
            SkuStock(team_id=other.id, sku_id=foreign_sku.id, on_order=99),
        ]
    )
    await async_db.flush()

    assert foreign_sku.id not in await LocationStockCRUD(async_db).on_hand_locations_by_sku_id()
    assert await SkuStockCRUD(async_db).on_order_by_sku_id([foreign_sku.id]) == {}
    selected = await query(
        owner_client, "skus", q="WORKSPACE-STOCK-SCOPE", sort={"field": "on_hand"}
    )
    assert [
        (row["id"], row["on_hand"], row["on_order"], row["stock_locations"])
        for row in selected["items"]
    ] == [(own["id"], "0", "0", [])]
    assert selected["selection_ids"] == [own["id"]]

    explicit = await prepare(
        owner_client, "skus", action="archive", ids=[own["id"]], revisions=selected["revisions"]
    )
    assert explicit["eligible_count"] == 1
    frozen = await prepare(
        owner_client, "skus", action="archive", selection_token=selected["selection_token"]
    )
    assert frozen["eligible_count"] == 1
    assert (await execute(owner_client, frozen, "skus"))["succeeded"] == [own["id"]]
    past = await query(owner_client, "skus", q="WORKSPACE-STOCK-SCOPE", lifecycle="archived")
    assert [(row["id"], row["on_hand"]) for row in past["items"]] == [(own["id"], "0")]
