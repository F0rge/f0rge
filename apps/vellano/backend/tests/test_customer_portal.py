"""Trade B2B portal — separate customer session, draft SO until staff confirm."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_till import _inventory_on_hand, _set_retail_price
from tests.test_transfers import _receive_qty_at_location


async def test_trade_portal_draft_order_staff_confirm_holds(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="PORTAL-SOFA",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    location_id = await _location_id_by_name(owner_client, "Kramerville")

    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Trade Studio", "customer_type": "trade", "email": "studio@example.com"},
    )
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["id"]
    portal_user = await owner_client.post(
        f"/api/v1/customers/{customer_id}/portal-users",
        json={"email": "designer@studio.example", "password": "portal-pass-1"},
    )
    assert portal_user.status_code == 201, portal_user.text

    async_client.cookies.clear()
    staff_quotes = await async_client.get("/api/v1/quotes")
    assert staff_quotes.status_code == 401

    login = await async_client.post(
        "/api/v1/portal/login",
        json={"email": "designer@studio.example", "password": "portal-pass-1"},
    )
    assert login.status_code == 200, login.text
    me = await async_client.get("/api/v1/portal/me")
    assert me.status_code == 200
    assert me.json()["customer_id"] == customer_id

    staff_surface = await async_client.get("/api/v1/quotes")
    assert staff_surface.status_code == 401

    catalogue = await async_client.get("/api/v1/portal/catalogue")
    assert catalogue.status_code == 200
    assert any(item["id"] == sku_id for item in catalogue.json())

    placed = await async_client.post(
        "/api/v1/portal/orders",
        json={"lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert placed.status_code == 201, placed.text
    draft = placed.json()
    assert draft["status"] == "draft"
    assert draft["hold_stock"] is False
    assert draft["so_number"].startswith("SO-")

    await _relogin_owner(owner_client)
    listed = await owner_client.get("/api/v1/orders")
    assert listed.status_code == 200
    assert any(
        item["id"] == draft["id"] and item["status"] == "draft" for item in listed.json()["items"]
    )

    on_hand_before = await _inventory_on_hand(owner_client, sku_id, location_id)
    confirmed = await owner_client.post(
        f"/api/v1/orders/{draft['id']}/confirm",
        json={"location_id": location_id, "hold_stock": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "open"
    assert confirmed.json()["hold_stock"] is True
    on_hand_after = await _inventory_on_hand(owner_client, sku_id, location_id)
    assert on_hand_after == on_hand_before - 1
