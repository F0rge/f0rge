"""V2-S13 SKU preferred supplier, lead time, and computed last landed cost."""

from __future__ import annotations

import uuid

from httpx import AsyncClient


async def _create_sku(owner_client: AsyncClient, suffix: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": f"VEL-SUP-{suffix}",
            "our_barcode": f"BAR-SUP-{suffix}",
            "name": f"Supplier test {suffix}",
            "design": f"Design {suffix}",
            "fabric": f"Fabric {suffix}",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_supplier(owner_client: AsyncClient, name: str) -> dict:
    resp = await owner_client.post("/api/v1/suppliers", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


async def _kramerville_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    for loc in resp.json():
        if loc["name"] == "Kramerville":
            return loc["id"]
    raise AssertionError("Kramerville not found")


async def test_patch_supplier_fields_get_and_list_include_values(
    owner_client: AsyncClient,
) -> None:
    supplier = await _create_supplier(owner_client, "Preferred Supplier Co")
    sku = await _create_sku(owner_client, "PATCH")

    patch_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={
            "preferred_supplier_id": supplier["id"],
            "lead_time_days": 21,
            "supplier_ref": "SUP-REF-42",
        },
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["preferred_supplier_id"] == supplier["id"]
    assert body["preferred_supplier_name"] == "Preferred Supplier Co"
    assert body["lead_time_days"] == 21
    assert body["supplier_ref"] == "SUP-REF-42"
    assert body["last_landed_cost_zar"] is None

    get_resp = await owner_client.get(f"/api/v1/skus/{sku['id']}")
    assert get_resp.status_code == 200
    got = get_resp.json()
    assert got["preferred_supplier_name"] == "Preferred Supplier Co"
    assert got["lead_time_days"] == 21

    list_resp = await owner_client.get("/api/v1/skus")
    assert list_resp.status_code == 200
    listed = next(item for item in list_resp.json() if item["id"] == sku["id"])
    assert listed["preferred_supplier_id"] == supplier["id"]
    assert listed["preferred_supplier_name"] == "Preferred Supplier Co"
    assert listed["supplier_ref"] == "SUP-REF-42"


async def test_patch_unknown_preferred_supplier_returns_404(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "404")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"preferred_supplier_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Supplier not found"


async def test_clear_supplier_fields_with_null(owner_client: AsyncClient) -> None:
    supplier = await _create_supplier(owner_client, "Clearable Supplier")
    sku = await _create_sku(owner_client, "CLEAR")

    set_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={
            "preferred_supplier_id": supplier["id"],
            "lead_time_days": 14,
            "supplier_ref": "TEMP-REF",
        },
    )
    assert set_resp.status_code == 200

    clear_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={
            "preferred_supplier_id": None,
            "lead_time_days": None,
            "supplier_ref": None,
        },
    )
    assert clear_resp.status_code == 200
    body = clear_resp.json()
    assert body["preferred_supplier_id"] is None
    assert body["preferred_supplier_name"] is None
    assert body["lead_time_days"] is None
    assert body["supplier_ref"] is None


async def test_last_landed_cost_null_for_opening_stock_only(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-OPEN-LAND",
            "our_barcode": "BAR-OPEN-LAND",
            "name": "Opening only",
            "design": "Opening design land",
            "fabric": "Opening fabric land",
            "opening_location_id": location_id,
            "opening_qty": 2,
            "opening_unit_cost_zar": "150.00",
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["last_landed_cost_zar"] is None

    get_resp = await owner_client.get(f"/api/v1/skus/{body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["last_landed_cost_zar"] is None


async def test_warehouse_cannot_patch_supplier_fields(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier = await _create_supplier(owner_client, "Warehouse Block Supplier")
    sku = await _create_sku(owner_client, "WH")

    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "warehouse-supplier@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-supplier@example.com", "password": "warehouse-password"},
    )
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={
            "preferred_supplier_id": supplier["id"],
            "lead_time_days": 7,
        },
    )
    assert patch_resp.status_code == 403


async def test_unauthenticated_patch_returns_401(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "UNAUTH")
    async_client.cookies.clear()
    resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"lead_time_days": 10},
    )
    assert resp.status_code == 401
