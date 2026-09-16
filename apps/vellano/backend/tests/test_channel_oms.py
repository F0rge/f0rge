"""Channel OMS: ATP, hashed keys, HMAC webhooks, GL 1150, fulfill, refund."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.channel_webhooks import verify_shopify_hmac
from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_till import _transfer_to_bedfordview
from tests.test_transfers import _on_hand, _receive_qty_at_location


def _shopify_hmac(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


class FakeShopify:
    def __init__(self) -> None:
        self.quantities: list[dict] = []
        self.fulfillments: list[str] = []

    async def set_available_quantities(self, quantities, reference) -> None:
        self.quantities.append({"quantities": quantities, "reference": reference})

    async def create_fulfillment(self, fulfillment_order_id: str) -> None:
        self.fulfillments.append(fulfillment_order_id)

    async def list_locations(self) -> list[dict]:
        return [{"gid": "gid://shopify/Location/1", "name": "Web"}]

    async def fulfillment_order_id_for_order(self, shopify_order_id: str) -> str:
        del shopify_order_id
        return "gid://shopify/FulfillmentOrder/99"

    async def graphql(self, query: str, variables=None) -> dict:
        del query, variables
        return {}


@pytest.fixture
def fake_shopify(monkeypatch: pytest.MonkeyPatch) -> FakeShopify:
    fake = FakeShopify()
    monkeypatch.setattr(
        "app.services.shopify_admin.ShopifyAdminClient",
        lambda *args, **kwargs: fake,
    )
    monkeypatch.setattr(
        "app.services.channel_outbox.ShopifyAdminClient",
        lambda *args, **kwargs: fake,
    )
    monkeypatch.setattr(settings, "shopify_shop_domain", "vellano-dev-store")
    monkeypatch.setattr(settings, "shopify_admin_token", "shpat_test")
    monkeypatch.setattr(settings, "shopify_webhook_secret", "hook-secret")
    return fake


async def _on_hand_or_zero(client: AsyncClient, sku_id: str, location_name: str) -> int:
    inv = await client.get("/api/v1/inventory")
    assert inv.status_code == 200
    row = next((item for item in inv.json() if item["sku_id"] == sku_id), None)
    if row is None:
        return 0
    loc = next(
        (item for item in row["locations"] if item["location_name"] == location_name),
        None,
    )
    return 0 if loc is None else loc["on_hand"]


async def _account_balance(client: AsyncClient, code: str) -> str:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    for account in resp.json():
        if account["code"] == code:
            return account["balance_zar"]
    raise AssertionError(f"Account {code} not found")


async def _login_till(client: AsyncClient) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "till@example.com", "password": settings.seed_till_password},
    )
    assert resp.status_code == 200
    return client


@pytest.mark.no_db
def test_shopify_hmac_accepts_matching_signature() -> None:
    body = b'{"id":1}'
    header = _shopify_hmac("hush", body)
    assert verify_shopify_hmac("hush", body, header)
    assert not verify_shopify_hmac("hush", body, "nope")
    assert not verify_shopify_hmac("", body, header)


async def test_channel_defaults_warehouse_only(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/channels")
    assert resp.status_code == 200
    body = resp.json()
    assert body["atp_mode"] == "warehouse_only"
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    assert body["atp_location_id"] == kramerville_id
    slugs = {row["slug"] for row in body["channels"]}
    assert slugs == {"shopify", "email", "manual"}


async def test_till_cannot_rotate_shopify_token(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    del owner_client
    till = await _login_till(async_client)
    resp = await till.patch(
        "/api/v1/channels/shopify",
        json={"shop_domain": "should-fail.myshopify.com"},
    )
    assert resp.status_code == 403


async def test_api_key_can_read_atp_not_shopify_settings(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    created = await owner_client.post("/api/v1/channels/api-keys", json={"name": "ingest"})
    assert created.status_code == 201
    token = created.json()["token"]
    assert token.startswith("velch_live_")
    async_client.cookies.clear()
    atp = await async_client.get(
        "/api/v1/channels/atp",
        headers={"X-Channel-Key": token},
    )
    assert atp.status_code == 200
    forbidden = await async_client.patch(
        "/api/v1/channels/shopify",
        json={"enabled": False},
        headers={"X-Channel-Key": token},
    )
    assert forbidden.status_code in (401, 403)


async def test_warehouse_only_sale_decrements_kramerville_not_bedfordview(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="CH-WH-ONLY",
    )
    sku_id = data["sku"]["id"]
    our_ref = data["sku"]["our_ref"]
    await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)
    await _relogin_owner(owner_client)
    await owner_client.post(
        "/api/v1/channels/listings",
        json={"sku_id": sku_id, "external_inventory_item_id": "gid://shopify/InventoryItem/1"},
    )
    sale = await owner_client.post(
        "/api/v1/channels/orders",
        json={
            "channel": "shopify",
            "external_id": "wh-only-1",
            "email": "web@example.com",
            "paid": True,
            "lines": [{"sku": our_ref, "qty": 1, "unit_inc_vat": "1150.00"}],
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["status"] == "posted"
    assert await _on_hand(owner_client, sku_id, "Kramerville") == 0
    assert await _on_hand(owner_client, sku_id, "Bedfordview") == 1


async def test_shopify_paid_order_posts_1150_and_decrements_stock(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="CH-GL-1150",
    )
    sku_id = data["sku"]["id"]
    our_ref = data["sku"]["our_ref"]
    before = await _account_balance(owner_client, "1150")
    sale = await owner_client.post(
        "/api/v1/channels/orders",
        json={
            "channel": "shopify",
            "external_id": "gl-1150-1",
            "email": "paid@example.com",
            "customer_name": "Web Customer",
            "paid": True,
            "lines": [{"sku": our_ref, "qty": 1, "unit_inc_vat": "1150.00"}],
        },
    )
    assert sale.status_code == 201, sale.text
    body = sale.json()
    assert body["status"] == "posted"
    assert body["invoice_id"]
    invoice = await owner_client.get(f"/api/v1/invoices/{body['invoice_id']}")
    assert invoice.status_code == 200
    assert invoice.json()["source"] == "shopify"
    after = await _account_balance(owner_client, "1150")
    assert after != before
    assert await _on_hand(owner_client, sku_id, "Kramerville") == 1


async def test_channel_order_external_id_is_idempotent(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=3,
        location_name="Kramerville",
        our_ref="CH-IDEM",
    )
    our_ref = data["sku"]["our_ref"]
    payload = {
        "channel": "shopify",
        "external_id": "idem-1",
        "email": "idem@example.com",
        "paid": True,
        "lines": [{"sku": our_ref, "qty": 1, "unit_inc_vat": "230.00"}],
    }
    first = await owner_client.post("/api/v1/channels/orders", json=payload)
    second = await owner_client.post("/api/v1/channels/orders", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["invoice_id"] == second.json()["invoice_id"]
    listed = await owner_client.get("/api/v1/channels/orders?q=idem-1")
    assert listed.json()["total"] == 1


async def test_unmapped_sku_parks_needs_mapping(
    owner_client: AsyncClient,
) -> None:
    sale = await owner_client.post(
        "/api/v1/channels/orders",
        json={
            "channel": "shopify",
            "external_id": "unmap-1",
            "email": "map@example.com",
            "paid": True,
            "lines": [{"sku": "NO-SUCH-SKU", "qty": 1, "unit_inc_vat": "100.00"}],
        },
    )
    assert sale.status_code == 201
    assert sale.json()["status"] == "needs_mapping"
    assert sale.json()["invoice_id"] is None


async def test_hmac_webhook_rejects_bad_signature(
    owner_client: AsyncClient,
    fake_shopify: FakeShopify,
) -> None:
    del fake_shopify
    body = json.dumps({"id": 9, "financial_status": "paid", "line_items": []}).encode()
    resp = await owner_client.post(
        "/api/v1/channels/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Topic": "orders/create",
            "X-Shopify-Hmac-Sha256": "invalid",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


async def test_hmac_webhook_ingests_paid_order_via_outbox(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    fake_shopify: FakeShopify,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="CH-HOOK",
    )
    our_ref = data["sku"]["our_ref"]
    payload = {
        "id": 88001,
        "email": "hook@example.com",
        "financial_status": "paid",
        "line_items": [
            {"sku": our_ref, "quantity": 1, "price": "460.00", "title": "Sofa", "variant_id": 11}
        ],
        "fulfillment_orders": [{"id": 77}],
    }
    body = json.dumps(payload).encode()
    resp = await owner_client.post(
        "/api/v1/channels/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Topic": "orders/create",
            "X-Shopify-Hmac-Sha256": _shopify_hmac("hook-secret", body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "accepted"
    drained = await owner_client.post("/api/v1/channels/outbox/drain")
    assert drained.status_code == 200
    order = await owner_client.get("/api/v1/channels/orders?q=88001")
    assert order.json()["total"] >= 1
    item = order.json()["items"][0]
    assert item["status"] == "posted"
    assert await _on_hand(owner_client, data["sku"]["id"], "Kramerville") == 1
    del fake_shopify


async def test_fulfill_calls_shopify_fulfillment_create(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    fake_shopify: FakeShopify,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="CH-FULFILL",
    )
    our_ref = data["sku"]["our_ref"]
    sale = await owner_client.post(
        "/api/v1/channels/orders",
        json={
            "channel": "shopify",
            "external_id": "ful-1",
            "email": "ful@example.com",
            "paid": True,
            "shopify_fulfillment_order_id": "gid://shopify/FulfillmentOrder/99",
            "lines": [{"sku": our_ref, "qty": 1, "unit_inc_vat": "230.00"}],
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["delivery_id"]
    fulfilled = await owner_client.post(f"/api/v1/channels/orders/{sale.json()['id']}/fulfill")
    assert fulfilled.status_code == 200, fulfilled.text
    assert fake_shopify.fulfillments == ["gid://shopify/FulfillmentOrder/99"]


async def test_cancel_restocks_and_credits(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="CH-REFUND",
    )
    sku_id = data["sku"]["id"]
    our_ref = data["sku"]["our_ref"]
    before_inv = await _account_balance(owner_client, "1300")
    before_cogs = await _account_balance(owner_client, "5000")
    sale = await owner_client.post(
        "/api/v1/channels/orders",
        json={
            "channel": "shopify",
            "external_id": "ref-1",
            "email": "ref@example.com",
            "paid": True,
            "lines": [{"sku": our_ref, "qty": 1, "unit_inc_vat": "230.00"}],
        },
    )
    assert sale.status_code == 201, sale.text
    assert await _on_hand_or_zero(owner_client, sku_id, "Kramerville") == 0
    cancelled = await owner_client.post(f"/api/v1/channels/orders/{sale.json()['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "refunded"
    assert await _on_hand_or_zero(owner_client, sku_id, "Kramerville") == 1
    after_inv = await _account_balance(owner_client, "1300")
    after_cogs = await _account_balance(owner_client, "5000")
    assert Decimal(after_inv) == Decimal(before_inv)
    assert Decimal(after_cogs) == Decimal(before_cogs)


async def test_refund_webhook_matches_order_id_not_refund_id(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    fake_shopify: FakeShopify,
) -> None:
    del fake_shopify
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="CH-REFUND-HOOK",
    )
    our_ref = data["sku"]["our_ref"]
    sale = await owner_client.post(
        "/api/v1/channels/orders",
        json={
            "channel": "shopify",
            "external_id": "99001",
            "email": "refund-hook@example.com",
            "paid": True,
            "lines": [{"sku": our_ref, "qty": 1, "unit_inc_vat": "230.00"}],
        },
    )
    assert sale.status_code == 201, sale.text
    payload = {"id": 555, "order_id": 99001}
    body = json.dumps(payload).encode()
    resp = await owner_client.post(
        "/api/v1/channels/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Topic": "refunds/create",
            "X-Shopify-Hmac-Sha256": _shopify_hmac("hook-secret", body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    order = await owner_client.get(f"/api/v1/channels/orders/{sale.json()['id']}")
    assert order.json()["status"] == "refunded"


async def test_partially_paid_webhook_does_not_post(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    fake_shopify: FakeShopify,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="CH-PARTIAL",
    )
    our_ref = data["sku"]["our_ref"]
    payload = {
        "id": 77001,
        "email": "partial@example.com",
        "financial_status": "partially_paid",
        "line_items": [
            {"sku": our_ref, "quantity": 1, "price": "230.00", "title": "Sofa", "variant_id": 11}
        ],
    }
    body = json.dumps(payload).encode()
    resp = await owner_client.post(
        "/api/v1/channels/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Topic": "orders/create",
            "X-Shopify-Hmac-Sha256": _shopify_hmac("hook-secret", body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200, resp.text
    drained = await owner_client.post("/api/v1/channels/outbox/drain")
    assert drained.status_code == 200
    order = await owner_client.get("/api/v1/channels/orders?q=77001")
    assert order.json()["total"] >= 1
    assert order.json()["items"][0]["status"] == "received"
    assert await _on_hand(owner_client, data["sku"]["id"], "Kramerville") == 1
    del fake_shopify


async def test_manual_channel_hits_bank_not_shopify_clearing(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="CH-MANUAL",
    )
    our_ref = data["sku"]["our_ref"]
    before_bank = await _account_balance(owner_client, "1100")
    before_clearing = await _account_balance(owner_client, "1150")
    sale = await owner_client.post(
        "/api/v1/channels/orders",
        json={
            "channel": "manual",
            "external_id": "man-1",
            "email": "manual@example.com",
            "paid": True,
            "lines": [{"sku": our_ref, "qty": 1, "unit_inc_vat": "230.00"}],
        },
    )
    assert sale.status_code == 201, sale.text
    assert await _account_balance(owner_client, "1100") != before_bank
    assert await _account_balance(owner_client, "1150") == before_clearing
