"""V2-S12 reorder minimum and draft PO creation."""

from __future__ import annotations

from tests.conftest import authenticate_as, create_test_staff

from decimal import Decimal
from typing import Optional
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.reorder import suggest_qty
from app.models.sku import Sku
from app.models.sku_supplier_price import SkuSupplierPrice

from tests.test_purchase_orders import _create_supplier, _relogin_owner


async def _kramerville_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    for loc in resp.json():
        if loc["name"] == "Kramerville":
            return loc["id"]
    raise AssertionError("Kramerville not found")


async def _create_buyer_s12(async_client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    await create_test_staff(
        owner_client,
        **{
            "email": "buyer-s12-ro@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "buyer-s12-ro@example.com")
    assert login_resp.status_code == 200
    return async_client


async def _create_warehouse_s12(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> AsyncClient:
    await _relogin_owner(owner_client)
    await create_test_staff(
        owner_client,
        **{
            "email": "warehouse-s12-ro@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "warehouse-s12-ro@example.com")
    assert login_resp.status_code == 200
    return async_client


async def _sku_with_opening(
    owner_client: AsyncClient,
    *,
    our_ref: str,
    opening_qty: int,
    reorder_min: Optional[int] = None,
    preferred_supplier_id: Optional[str] = None,
) -> dict:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": our_ref,
            "our_barcode": f"{our_ref}-BAR",
            "name": f"Reorder {our_ref}",
            "design": f"Design {our_ref}",
            "fabric": f"Fabric {our_ref}",
            "opening_location_id": location_id,
            "opening_qty": opening_qty,
            "opening_unit_cost_zar": "100.00",
        },
    )
    assert create_resp.status_code == 201
    sku = create_resp.json()

    patch_payload: dict = {}
    if reorder_min is not None:
        patch_payload["reorder_min"] = reorder_min
    if preferred_supplier_id is not None:
        patch_payload["preferred_supplier_id"] = preferred_supplier_id
    if patch_payload:
        patch_resp = await owner_client.patch(f"/api/v1/skus/{sku['id']}", json=patch_payload)
        assert patch_resp.status_code == 200
        sku = patch_resp.json()

    return sku


async def test_patch_reorder_min_lists_sku_with_correct_suggested_qty(
    owner_client: AsyncClient,
) -> None:
    supplier = await _create_supplier(owner_client, "Reorder Supplier A")
    sku = await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-001",
        opening_qty=3,
        reorder_min=10,
        preferred_supplier_id=supplier,
    )

    resp = await owner_client.get("/api/v1/reorder")
    assert resp.status_code == 200
    item = next(row for row in resp.json() if row["sku_id"] == sku["id"])
    assert item["reorder_min"] == 10
    assert item["on_hand"] == 3
    assert item["on_order"] == 0
    assert item["suggested_qty"] == 7
    assert item["preferred_supplier_id"] == supplier
    assert item["preferred_supplier_name"] == "Reorder Supplier A"


async def test_sku_at_or_above_min_and_null_reorder_min_not_listed(
    owner_client: AsyncClient,
) -> None:
    supplier = await _create_supplier(owner_client, "Reorder Supplier B")
    at_min = await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-AT-MIN",
        opening_qty=5,
        reorder_min=5,
        preferred_supplier_id=supplier,
    )
    above_min = await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-ABOVE",
        opening_qty=8,
        reorder_min=5,
        preferred_supplier_id=supplier,
    )
    no_min = await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-NO-MIN",
        opening_qty=1,
    )

    resp = await owner_client.get("/api/v1/reorder")
    assert resp.status_code == 200
    listed_ids = {row["sku_id"] for row in resp.json()}
    assert at_min["id"] not in listed_ids
    assert above_min["id"] not in listed_ids
    assert no_min["id"] not in listed_ids


async def test_open_po_qty_counts_as_on_order(owner_client: AsyncClient) -> None:
    supplier = await _create_supplier(owner_client, "Reorder Supplier C")
    sku = await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-OPEN-PO",
        opening_qty=2,
        reorder_min=10,
        preferred_supplier_id=supplier,
    )

    before = await owner_client.get("/api/v1/reorder")
    assert before.status_code == 200
    before_item = next(row for row in before.json() if row["sku_id"] == sku["id"])
    assert before_item["suggested_qty"] == 8

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier,
            "lines": [{"sku_id": sku["id"], "qty": 5, "factory_unit_amount": "50.00"}],
        },
    )
    assert po_resp.status_code == 201

    after = await owner_client.get("/api/v1/reorder")
    assert after.status_code == 200
    after_item = next(row for row in after.json() if row["sku_id"] == sku["id"])
    assert after_item["on_order"] == 5
    assert after_item["suggested_qty"] == 3


async def test_draft_po_creates_open_po_with_suggested_qty_and_unit_one(
    owner_client: AsyncClient,
) -> None:
    supplier = await _create_supplier(owner_client, "Reorder Supplier D")
    sku = await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-DRAFT",
        opening_qty=4,
        reorder_min=10,
        preferred_supplier_id=supplier,
    )

    resp = await owner_client.post(
        "/api/v1/reorder/draft-po",
        json={"sku_ids": [sku["id"]]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["purchase_orders"]) == 1
    po = body["purchase_orders"][0]
    assert po["status"] == "open"
    assert po["supplier_id"] == supplier
    assert len(po["lines"]) == 1
    line = po["lines"][0]
    assert line["sku_id"] == sku["id"]
    assert line["qty"] == 6
    assert line["factory_unit_amount"] == "1"


async def test_draft_po_missing_preferred_supplier_returns_400(
    owner_client: AsyncClient,
) -> None:
    sku = await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-NO-SUP",
        opening_qty=1,
        reorder_min=5,
    )

    resp = await owner_client.post(
        "/api/v1/reorder/draft-po",
        json={"sku_ids": [sku["id"]]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Preferred supplier is required"


async def test_warehouse_cannot_post_draft_po_but_can_get(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    warehouse_client = await _create_warehouse_s12(async_client, owner_client)

    get_resp = await warehouse_client.get("/api/v1/reorder")
    assert get_resp.status_code == 200

    post_resp = await warehouse_client.post(
        "/api/v1/reorder/draft-po",
        json={"sku_ids": ["00000000-0000-0000-0000-000000000001"]},
    )
    assert post_resp.status_code == 403


async def test_unauthenticated_get_reorder_returns_401(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _sku_with_opening(
        owner_client,
        our_ref="RO-S12-UNAUTH",
        opening_qty=1,
        reorder_min=5,
    )
    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    resp = await async_client.get("/api/v1/reorder")
    assert resp.status_code == 401


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("need", "min_order", "pack", "expected"),
    [
        # No price row for the preferred supplier: the need itself, fractions included.
        ("7", None, None, "7"),
        ("2.5", None, None, "2.5"),
        # Rounded up to the pack multiple.
        ("7", None, 4, "8"),
        ("8", None, 4, "8"),
        ("2.5", None, 1, "3"),
        # Raised to the minimum order.
        ("3", 10, None, "10"),
        ("12", 10, None, "12"),
        # Both: the minimum order is itself rounded up to the pack multiple.
        ("3", 10, 4, "12"),
        ("13", 10, 4, "16"),
    ],
)
def test_suggest_qty_rounds_for_the_supplier(need, min_order, pack, expected) -> None:
    assert suggest_qty(Decimal(need), min_order, pack) == Decimal(expected)


async def _reorder_item(client: AsyncClient, sku_id: str) -> Optional[dict]:
    resp = await client.get("/api/v1/reorder")
    assert resp.status_code == 200
    return next((row for row in resp.json() if row["sku_id"] == sku_id), None)


async def _set_supply(db: AsyncSession, sku_id: str, supplier_id: Optional[str], **fields) -> None:
    sku = await db.get(Sku, UUID(sku_id))
    assert sku is not None
    for key in ("order_up_to", "do_not_reorder"):
        if key in fields:
            setattr(sku, key, fields.pop(key))
    if supplier_id is not None:
        db.add(SkuSupplierPrice(sku_id=sku.id, supplier_id=UUID(supplier_id), **fields))
    await db.flush()


async def test_order_up_to_and_supplier_rounding_shape_the_suggestion(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    supplier = await _create_supplier(owner_client, "Reorder Supplier Packs")
    other = await _create_supplier(owner_client, "Reorder Supplier Other")

    async def listed(ref: str, opening: int, reorder_min: int) -> str:
        sku = await _sku_with_opening(
            owner_client,
            our_ref=ref,
            opening_qty=opening,
            reorder_min=reorder_min,
            preferred_supplier_id=supplier,
        )
        return sku["id"]

    # Below the minimum without order-up-to: need = reorder_min - stock.
    plain = await listed("RO-PLAIN", 3, 10)
    # With order-up-to: need = order_up_to - stock.
    up_to = await listed("RO-UPTO", 3, 10)
    await _set_supply(async_db, up_to, None, order_up_to=20)
    packed = await listed("RO-PACK", 3, 10)
    await _set_supply(async_db, packed, supplier, pack_multiple=4)
    minimum = await listed("RO-MOQ", 8, 10)
    await _set_supply(async_db, minimum, supplier, min_order_qty=10)
    both = await listed("RO-BOTH", 8, 10)
    await _set_supply(async_db, both, supplier, order_up_to=12, min_order_qty=5, pack_multiple=4)
    # A price row for another supplier does not apply.
    elsewhere = await listed("RO-ELSEWHERE", 3, 10)
    await _set_supply(async_db, elsewhere, other, pack_multiple=50)
    stopped = await listed("RO-STOPPED", 3, 10)
    await _set_supply(async_db, stopped, None, do_not_reorder=True)

    def shape(item: dict) -> tuple:
        return (
            item["order_up_to"],
            item["need_qty"],
            item["min_order_qty"],
            item["pack_multiple"],
            item["suggested_qty"],
        )

    assert shape(await _reorder_item(owner_client, plain)) == (None, 7, None, None, 7)
    assert shape(await _reorder_item(owner_client, up_to)) == (20, 17, None, None, 17)
    assert shape(await _reorder_item(owner_client, packed)) == (None, 7, None, 4, 8)
    assert shape(await _reorder_item(owner_client, minimum)) == (None, 2, 10, None, 10)
    assert shape(await _reorder_item(owner_client, both)) == (12, 4, 5, 4, 8)
    assert shape(await _reorder_item(owner_client, elsewhere)) == (None, 7, None, None, 7)
    # Do not reorder: still sells, never listed.
    assert await _reorder_item(owner_client, stopped) is None

    resp = await owner_client.post(
        "/api/v1/reorder/draft-po", json={"sku_ids": [plain, up_to, packed, minimum, both]}
    )
    assert resp.status_code == 201, resp.text
    [po] = resp.json()["purchase_orders"]
    quantities = {line["sku_id"]: line["qty"] for line in po["lines"]}
    assert quantities == {plain: 7, up_to: 17, packed: 8, minimum: 10, both: 8}
    refused = await owner_client.post("/api/v1/reorder/draft-po", json={"sku_ids": [stopped]})
    assert refused.status_code == 400
