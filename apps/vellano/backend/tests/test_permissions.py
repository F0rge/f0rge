"""F5 permission catalog and custom roles."""

from __future__ import annotations

from httpx import AsyncClient

from app.config import settings
from app.permissions import PERMISSION_CATALOG, ROLE_PRESETS, SLUG_OWNER, TILL_SELL
from tests.test_purchase_orders import (
    _create_till,
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_transfers import _receive_qty_at_location, complete_location_transfer


SHOWROOM_TILL_KEYS = [
    "till.sell",
    "sales.returns",
    "sales.laybys",
    "sales.deliveries",
    "sales.customers",
]


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def _stocked_sku_at_bedford(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
) -> tuple[str, str]:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref=our_ref,
    )
    sku_id = data["sku"]["id"]
    patch = await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"retail_ex_vat": "1000.00"})
    assert patch.status_code == 200
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    await complete_location_transfer(
        owner_client,
        kramerville_id,
        bedford_id,
        sku_id,
        2,
    )
    return sku_id, bedford_id


async def test_warehouse_forbidden_till_sell(async_client: AsyncClient) -> None:
    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    resp = await async_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": "00000000-0000-4000-8000-000000000001",
            "lines": [{"sku_id": "00000000-0000-4000-8000-000000000002", "qty": 1}],
            "tender": "cash",
        },
    )
    assert resp.status_code == 403


async def test_books_forbidden_till_sell(async_client: AsyncClient) -> None:
    await _login(async_client, "books@example.com", settings.seed_books_password)
    resp = await async_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": "00000000-0000-4000-8000-000000000001",
            "lines": [{"sku_id": "00000000-0000-4000-8000-000000000002", "qty": 1}],
            "tender": "cash",
        },
    )
    assert resp.status_code == 403


async def test_till_sell_discount_zero_ok(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "PERM-TILL0")
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201


async def test_custom_showroom_till_no_discount_or_cost(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "PERM-SHOW")
    created = await owner_client.post(
        "/api/v1/roles",
        json={"name": "Showroom till", "permissions": SHOWROOM_TILL_KEYS},
    )
    assert created.status_code == 201
    role = created.json()
    assert role["slug"] == "showroom-till"
    assert "till.discount" not in role["permissions"]
    assert "stock.cost.view" not in role["permissions"]

    user_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "showroom-till@example.com",
            "password": "showroom-password",
            "role": role["slug"],
        },
    )
    assert user_resp.status_code == 201

    await _login(async_client, "showroom-till@example.com", "showroom-password")
    me = await async_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "showroom-till"
    assert "till.discount" not in me.json()["permissions"]

    ok_sale = await async_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
        },
    )
    assert ok_sale.status_code == 201

    denied = await async_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "10"}],
            "tender": "cash",
        },
    )
    assert denied.status_code == 403

    audit = await async_client.get(f"/api/v1/skus/{sku_id}/cost-audit")
    assert audit.status_code == 403


async def test_owner_has_every_key_and_cannot_strip_or_demote(
    owner_client: AsyncClient,
) -> None:
    me = await owner_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert set(me.json()["permissions"]) == set(PERMISSION_CATALOG)
    assert set(ROLE_PRESETS[SLUG_OWNER]) == set(PERMISSION_CATALOG)

    roles = await owner_client.get("/api/v1/roles")
    assert roles.status_code == 200
    owner_role = next(role for role in roles.json() if role["slug"] == "owner")
    assert owner_role["is_system"] is True
    assert owner_role["is_owner_preset"] is True

    strip = await owner_client.patch(
        f"/api/v1/roles/{owner_role['id']}",
        json={"permissions": [TILL_SELL]},
    )
    assert strip.status_code == 409

    delete = await owner_client.delete(f"/api/v1/roles/{owner_role['id']}")
    assert delete.status_code == 409

    demote = await owner_client.patch(
        f"/api/v1/users/{me.json()['id']}",
        json={"role": "buyer"},
    )
    assert demote.status_code == 409


async def test_till_forbidden_roles_and_users(async_client: AsyncClient) -> None:
    await _login(async_client, "till@example.com", settings.seed_till_password)
    assert (await async_client.get("/api/v1/roles")).status_code == 403
    assert (await async_client.get("/api/v1/users")).status_code == 403
    assert (
        await async_client.post(
            "/api/v1/users",
            json={"email": "nope@example.com", "password": "nope-pass", "role": "till"},
        )
    ).status_code == 403


async def test_cannot_delete_system_buyer_role(owner_client: AsyncClient) -> None:
    roles = await owner_client.get("/api/v1/roles")
    assert roles.status_code == 200
    buyer = next(role for role in roles.json() if role["slug"] == "buyer")
    resp = await owner_client.delete(f"/api/v1/roles/{buyer['id']}")
    assert resp.status_code == 409


async def test_cannot_delete_assigned_custom_role(
    owner_client: AsyncClient,
) -> None:
    created = await owner_client.post(
        "/api/v1/roles",
        json={"name": "Temp assigned", "permissions": ["till.sell"]},
    )
    assert created.status_code == 201
    slug = created.json()["slug"]
    role_id = created.json()["id"]
    user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "temp-assigned@example.com",
            "password": "temp-password",
            "role": slug,
        },
    )
    assert user.status_code == 201
    denied = await owner_client.delete(f"/api/v1/roles/{role_id}")
    assert denied.status_code == 409


async def test_warehouse_inventory_hides_unit_cost(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="PERM-HIDE",
    )
    sku_id = data["sku"]["id"]
    owner_inv = await owner_client.get("/api/v1/inventory")
    assert owner_inv.status_code == 200
    owner_row = next(item for item in owner_inv.json() if item["sku_id"] == sku_id)
    assert owner_row["unit_cost_zar"] is not None

    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    hidden = await async_client.get("/api/v1/inventory")
    assert hidden.status_code == 200
    row = next(item for item in hidden.json() if item["sku_id"] == sku_id)
    assert row["unit_cost_zar"] is None
    assert all(loc["unit_cost_zar"] is None for loc in row["locations"])

    sku = await async_client.get(f"/api/v1/skus/{sku_id}")
    assert sku.status_code == 200
    assert sku.json()["last_landed_cost_zar"] is None

    await _relogin_owner(owner_client)
