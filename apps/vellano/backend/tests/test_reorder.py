"""V2-S12 reorder minimum and draft PO creation."""

from __future__ import annotations

from typing import Optional

from httpx import AsyncClient

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
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-s12-ro@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-s12-ro@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _create_warehouse_s12(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "warehouse-s12-ro@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-s12-ro@example.com", "password": "warehouse-password"},
    )
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
    resp = await async_client.get("/api/v1/reorder")
    assert resp.status_code == 401
