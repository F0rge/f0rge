"""SKU overview, supplier price rows, and the catalogue workspace's new fields."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.customer import Customer
from app.models.layby import Layby, LaybyLine, LaybyStatus
from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderStatus
from app.models.sku import Sku
from app.models.stock_reservation import StockReservation
from app.models.team import Team
from app.models.user import User
from tests.catalogue_lists import ensure_category, ensure_material
from tests.conftest import OWNER_EMAIL, authenticate_as
from tests.test_purchase_orders import _create_supplier, _location_id_by_name
from tests.test_record_workspace import query

SKUS = "/api/v1/skus"


async def _sku(client: AsyncClient, ref: str, **extra: object) -> dict:
    response = await client.post(
        SKUS, json={"our_ref": ref, "name": f"Item {ref}", "design": ref, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _as(client: AsyncClient, email: str) -> None:
    client.cookies.clear()
    client.headers.pop("Authorization", None)
    assert (await authenticate_as(client, email)).status_code == 200


async def _documents_holding(db, sku_id: uuid.UUID, location_id: uuid.UUID) -> None:
    owner = await db.scalar(select(User).where(User.email == OWNER_EMAIL))
    customer = Customer(name="Overview customer")
    db.add(customer)
    await db.flush()
    totals = dict(
        subtotal_ex_vat=Decimal(0),
        vat_amount=Decimal(0),
        total_inc_vat=Decimal(0),
        vat_rate=Decimal("0.15"),
    )
    order = SalesOrder(
        so_number="SO-OVR-1", customer_id=customer.id, status=SalesOrderStatus.OPEN, **totals
    )
    cancelled = SalesOrder(
        so_number="SO-OVR-2", customer_id=customer.id, status=SalesOrderStatus.CANCELLED, **totals
    )
    layby = Layby(
        layby_number="LB-OVR-1",
        customer_id=customer.id,
        location_id=location_id,
        due_date=datetime.date.today(),
        hold_stock=True,
        status=LaybyStatus.OPEN,
        created_by_user_id=owner.id,
        **totals,
    )
    unheld = Layby(
        layby_number="LB-OVR-2",
        customer_id=customer.id,
        location_id=location_id,
        due_date=datetime.date.today(),
        hold_stock=False,
        status=LaybyStatus.OPEN,
        created_by_user_id=owner.id,
        **totals,
    )
    db.add_all([order, cancelled, layby, unheld])
    await db.flush()
    line = dict(sku_id=sku_id, unit_ex_vat=Decimal(1), description="x")
    db.add_all(
        [
            SalesOrderLine(sales_order_id=order.id, qty=3, held_qty=2, **line),
            SalesOrderLine(sales_order_id=cancelled.id, qty=5, held_qty=5, **line),
            LaybyLine(layby_id=layby.id, sku_id=sku_id, qty=1, unit_ex_vat=Decimal(1)),
            LaybyLine(layby_id=unheld.id, sku_id=sku_id, qty=4, unit_ex_vat=Decimal(1)),
            # A live till reservation lowers availability, not on-hand.
            StockReservation(
                sku_id=sku_id,
                qty=2,
                holder_kind="basket",
                holder_id=uuid.uuid4(),
                location_id=location_id,
                expires_at=None,
            ),
        ]
    )
    await db.flush()


async def test_overview_stock_kits_prices_and_activity(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    kramerville = await _location_id_by_name(owner_client, "Kramerville")
    sku = await _sku(
        owner_client,
        "OVR-1",
        opening_location_id=kramerville,
        opening_qty=10,
        opening_unit_cost_zar="100.00",
    )
    sku_id = uuid.UUID(sku["id"])
    supplier_id = await _create_supplier(owner_client, "Overview Supplier")
    await owner_client.patch(
        f"{SKUS}/{sku['id']}", json={"preferred_supplier_id": supplier_id, "lead_time_days": 30}
    )
    po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 3, "factory_unit_amount": "10.00"}],
        },
    )
    assert po.status_code == 201, po.text
    kit = await _sku(owner_client, "OVR-KIT")
    bom = await owner_client.put(
        f"{SKUS}/{kit['id']}/bom", json={"lines": [{"component_sku_id": sku["id"], "qty": 2}]}
    )
    assert bom.status_code == 200, bom.text
    saved = await owner_client.put(
        f"{SKUS}/{sku['id']}/supplier-prices",
        json={
            "rows": [
                {
                    "supplier_id": supplier_id,
                    "supplier_sku": "OV-1",
                    "latest_price": "12.5",
                    "min_order_qty": 6,
                    "pack_multiple": 3,
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    await _documents_holding(db, sku_id, uuid.UUID(kramerville))

    response = await owner_client.get(f"{SKUS}/{sku['id']}/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sku"]["our_ref"] == "OVR-1"
    stock = body["stock"]
    assert stock["on_hand"] == 10
    assert stock["held"] == 3
    assert [(d["kind"], d["number"], d["qty"]) for d in stock["held_documents"]] == [
        ("sales_order", "SO-OVR-1", 2),
        ("layby", "LB-OVR-1", 1),
    ]
    assert stock["available"] == 8  # 10 at Kramerville minus the live reservation of 2
    assert stock["on_order"] == 3
    arrival = stock["next_arrival"]
    assert (arrival["po_number"], arrival["status"], arrival["qty"]) == (
        po.json()["po_number"],
        "open",
        3,
    )
    ordered = datetime.datetime.fromisoformat(po.json()["ordered_at"]).date()
    assert arrival["expected_on"] == (ordered + datetime.timedelta(days=30)).isoformat()
    assert arrival["expected_on_basis"] == "planned_lead_time"
    assert stock["unit_cost_zar"] is not None
    assert stock["locations"][0]["location_name"] == "Kramerville"
    assert stock["locations"][0]["unit_cost_zar"] is not None
    assert stock["locations"][0]["bins"][0]["code"] == "FLOOR"
    assert body["is_kit"] is False
    assert body["used_in_kits"] == [
        {
            "parent_sku_id": kit["id"],
            "our_ref": "OVR-KIT",
            "name": "Item OVR-KIT",
            "qty": 2.0,
            "parent_is_archived": False,
        }
    ]
    [price] = body["supplier_prices"]
    assert (price["is_preferred"], price["min_order_qty"], price["pack_multiple"]) == (True, 6, 3)
    assert Decimal(price["latest_price"]) == Decimal("12.5")
    [opening] = body["activity"]
    assert (opening["source"], opening["source_label"]) == ("opening", "Opening stock")
    assert opening["location_name"] == "Kramerville"
    assert opening["new_cost_zar"] is not None
    assert "qty" not in opening

    # The catalogue row and the overview agree on "on order" and "available".
    rows = await query(owner_client, "skus", q="OVR-1")
    row = next(item for item in rows["items"] if item["id"] == sku["id"])
    assert (Decimal(row["on_order"]), Decimal(row["available"])) == (Decimal(3), Decimal(8))

    # Without stock.cost.view: costs are masked, everything else stays.
    await _as(owner_client, "warehouse@example.com")
    masked = (await owner_client.get(f"{SKUS}/{sku['id']}/overview")).json()
    assert masked["stock"]["unit_cost_zar"] is None
    assert masked["stock"]["locations"][0]["unit_cost_zar"] is None
    assert masked["supplier_prices"][0]["latest_price"] is None
    assert masked["supplier_prices"][0]["min_order_qty"] == 6
    assert masked["activity"][0]["new_cost_zar"] is None
    assert masked["stock"]["held"] == 3
    await _as(owner_client, OWNER_EMAIL)


async def test_overview_next_arrival_without_a_derivable_date(owner_client) -> None:
    sku = await _sku(owner_client, "OVR-NODATE")
    assert (await owner_client.get(f"{SKUS}/{sku['id']}/overview")).json()["stock"][
        "next_arrival"
    ] is None
    supplier_id = await _create_supplier(owner_client, "No lead time supplier")
    po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "5.00"}],
        },
    )
    assert po.status_code == 201
    arrival = (await owner_client.get(f"{SKUS}/{sku['id']}/overview")).json()["stock"][
        "next_arrival"
    ]
    # No planned lead time on the SKU: no date is invented.
    assert (arrival["expected_on"], arrival["expected_on_basis"]) == (None, None)


async def test_overview_archived_foreign_and_anonymous(owner_client, async_client) -> None:
    db = owner_client.test_db
    sku = await _sku(owner_client, "OVR-ARCH")
    row = await db.get(Sku, uuid.UUID(sku["id"]))
    row.is_archived = True
    other = Team(name="Overview other organisation", slug="overview-other-org")
    db.add(other)
    await db.flush()
    foreign = Sku(
        team_id=other.id,
        our_ref="OVR-FOREIGN",
        our_barcode="OVR-FOREIGN",
        name="Foreign",
        design="Foreign",
        fabric="-",
    )
    db.add(foreign)
    await db.flush()

    archived = await owner_client.get(f"{SKUS}/{sku['id']}/overview")
    assert archived.status_code == 200
    assert archived.json()["sku"]["is_archived"] is True
    assert (await owner_client.get(f"{SKUS}/{foreign.id}/overview")).status_code == 404
    assert (await owner_client.get(f"{SKUS}/{foreign.id}/supplier-prices")).status_code == 404
    owner_client.cookies.clear()
    owner_client.headers.pop("Authorization", None)
    assert (await owner_client.get(f"{SKUS}/{sku['id']}/overview")).status_code == 401
    assert (await owner_client.get(f"{SKUS}/{sku['id']}/supplier-prices")).status_code == 401
    await _as(owner_client, OWNER_EMAIL)


async def test_supplier_price_rows_replace_and_validate(owner_client) -> None:
    sku = await _sku(owner_client, "OVR-SP")
    url = f"{SKUS}/{sku['id']}/supplier-prices"
    first = await _create_supplier(owner_client, "SP First")
    second = await _create_supplier(owner_client, "SP Second")
    await owner_client.patch(f"{SKUS}/{sku['id']}", json={"preferred_supplier_id": second})

    saved = await owner_client.put(
        url,
        json={
            "rows": [
                {"supplier_id": first, "latest_price": "10", "fixed_price": "9"},
                {"supplier_id": second, "min_order_qty": 4, "pack_multiple": 2},
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    # Preferred supplier first: that row is what reorder reads.
    assert [(r["supplier_name"], r["is_preferred"]) for r in saved.json()] == [
        ("SP Second", True),
        ("SP First", False),
    ]
    replaced = await owner_client.put(url, json={"rows": [{"supplier_id": second}]})
    assert [r["supplier_id"] for r in replaced.json()] == [second]
    assert replaced.json()[0]["min_order_qty"] is None
    assert (await owner_client.get(url)).json() == replaced.json()

    twice = await owner_client.put(
        url, json={"rows": [{"supplier_id": first}, {"supplier_id": first}]}
    )
    assert twice.status_code == 422
    assert twice.json()["detail"][0]["loc"] == ["body", "rows"]
    unknown = await owner_client.put(url, json={"rows": [{"supplier_id": str(uuid.uuid4())}]})
    assert unknown.status_code == 422
    assert unknown.json()["detail"][0]["loc"] == ["body", "rows", 0, "supplier_id"]
    zero = await owner_client.put(url, json={"rows": [{"supplier_id": first, "pack_multiple": 0}]})
    assert zero.status_code == 422
    negative = await owner_client.put(
        url, json={"rows": [{"supplier_id": first, "latest_price": "-1"}]}
    )
    assert negative.status_code == 422


async def test_supplier_prices_without_cost_view(owner_client, async_client) -> None:
    sku = await _sku(owner_client, "OVR-SP-COST")
    url = f"{SKUS}/{sku['id']}/supplier-prices"
    supplier = await _create_supplier(owner_client, "SP Cost")
    other = await _create_supplier(owner_client, "SP Cost Other")
    await owner_client.put(url, json={"rows": [{"supplier_id": supplier, "latest_price": "50"}]})

    # catalogue.mutate without stock.cost.view (a custom role).
    role = await owner_client.post(
        "/api/v1/roles", json={"name": "Catalogue clerk", "permissions": ["catalogue.mutate"]}
    )
    assert role.status_code == 201, role.text
    from tests.conftest import create_test_staff

    await create_test_staff(owner_client, email="clerk@example.com", role=role.json()["slug"])
    await _as(owner_client, "clerk@example.com")
    rows = (await owner_client.get(url)).json()
    assert rows[0]["latest_price"] is None
    # Quantities are editable; null prices keep the stored ones.
    edited = await owner_client.put(
        url, json={"rows": [{"supplier_id": supplier, "min_order_qty": 2, "pack_multiple": 2}]}
    )
    assert edited.status_code == 200, edited.text
    priced = await owner_client.put(
        url, json={"rows": [{"supplier_id": supplier, "latest_price": "1"}]}
    )
    assert priced.status_code == 403
    dropped = await owner_client.put(url, json={"rows": [{"supplier_id": other}]})
    assert dropped.status_code == 403

    await _as(owner_client, "warehouse@example.com")
    assert (await owner_client.put(url, json={"rows": []})).status_code == 403

    await _as(owner_client, OWNER_EMAIL)
    kept = (await owner_client.get(url)).json()[0]
    assert Decimal(kept["latest_price"]) == Decimal("50")
    assert (kept["min_order_qty"], kept["pack_multiple"]) == (2, 2)


async def test_workspace_filters_and_sorts_new_fields(owner_client) -> None:
    sofas = await ensure_category(owner_client, "WS Sofas")
    corner = await ensure_category(owner_client, "WS Corner", parent_id=sofas.id)
    linen = await ensure_material(owner_client, "WS Linen", "fabric")
    oak = await ensure_material(owner_client, "WS Oak", "wood")
    first = await _sku(
        owner_client,
        "WSF-1",
        category_id=str(sofas.id),
        subcategory_id=str(corner.id),
        colour_name="Oat",
        main_material_id=str(linen.id),
        other_material_ids=[str(oak.id)],
        do_not_reorder=True,
    )
    second = await _sku(owner_client, "WSF-2", main_material_id=str(oak.id))
    third = await _sku(owner_client, "WSF-3")

    async def ids(*filters: dict, **body: object) -> list[str]:
        result = await query(owner_client, "skus", q="WSF-", filters=list(filters), **body)
        return [row["id"] for row in result["items"]]

    # Material matches the main material or any other material.
    assert set(await ids({"field": "material", "operator": "eq", "value": "ws oak"})) == {
        first["id"],
        second["id"],
    }
    assert await ids({"field": "material", "operator": "ne", "value": "WS Oak"}) == [third["id"]]
    assert await ids({"field": "main_material", "operator": "eq", "value": "WS Linen"}) == [
        first["id"]
    ]
    assert await ids({"field": "material_family", "operator": "eq", "value": "wood"}) == [
        second["id"]
    ]
    assert await ids({"field": "subcategory", "operator": "eq", "value": "WS Corner"}) == [
        first["id"]
    ]
    assert await ids({"field": "colour_name", "operator": "contains", "value": "oa"}) == [
        first["id"]
    ]
    assert await ids({"field": "do_not_reorder", "operator": "eq", "value": True}) == [first["id"]]
    assert set(await ids({"field": "available", "operator": "lte", "value": 0})) == {
        first["id"],
        second["id"],
        third["id"],
    }
    sorted_ids = await ids(sort={"field": "main_material", "direction": "asc"})
    assert sorted_ids == [first["id"], second["id"], third["id"]]
    # Free text finds the main material by name.
    by_text = await query(owner_client, "skus", q="WS Linen")
    assert [row["id"] for row in by_text["items"]] == [first["id"]]
