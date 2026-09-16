"""Lookbook S5 — public request becomes a snapshot-priced draft quote."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient

from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from tests.test_lookbooks import _retail_sku
from tests.test_quotes import _named_customer, _walk_in_id


async def test_walk_in_request_uses_seeded_customer(owner_client: AsyncClient) -> None:
    walk_in_id = await _walk_in_id(owner_client)
    sku = await _retail_sku(owner_client, "LB-RQ-WALK")
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Walk request", "price_mode": "retail", "sku_ids": [sku["id"]]},
    )
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    requested = await owner_client.post(
        f"/api/v1/public/lookbooks/{token}/request",
        json={"name": "Ada", "contact": "0831112222", "sku_ids": [sku["id"]]},
    )
    assert requested.status_code == 204, requested.text

    activity = await owner_client.get(f"/api/v1/lookbooks/{created.json()['id']}/activity")
    assert activity.status_code == 200
    quotes = activity.json()["quotes"]
    assert len(quotes) == 1
    assert quotes[0]["quote_number"].startswith("QT-")
    assert activity.json()["submits"] == 1

    quote = await owner_client.get(f"/api/v1/quotes/{quotes[0]['id']}")
    assert quote.status_code == 200, quote.text
    body = quote.json()
    assert body["customer_id"] == walk_in_id
    assert body["customer_name"] == WALK_IN_CUSTOMER_NAME
    assert body["status"] == "draft"
    assert "Ada" in (body["notes"] or "")
    assert "0831112222" in (body["notes"] or "")
    assert body["lines"][0]["unit_ex_vat"] == "1000.00"
    assert "QT-" not in requested.text


async def test_crm_lookbook_request_keeps_customer(owner_client: AsyncClient) -> None:
    customer_id = await _named_customer(owner_client, "Lookbook Patel")
    sku = await _retail_sku(owner_client, "LB-RQ-CRM")
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "CRM request",
            "customer_id": customer_id,
            "price_mode": "retail",
            "sku_ids": [sku["id"]],
        },
    )
    assert created.status_code == 201, created.text
    requested = await owner_client.post(
        f"/api/v1/public/lookbooks/{created.json()['token']}/request",
        json={"name": "Patel", "contact": "patel@example.com", "sku_ids": [sku["id"]]},
    )
    assert requested.status_code == 204, requested.text
    activity = await owner_client.get(f"/api/v1/lookbooks/{created.json()['id']}/activity")
    quote = await owner_client.get(f"/api/v1/quotes/{activity.json()['quotes'][0]['id']}")
    assert quote.json()["customer_id"] == customer_id
    assert quote.json()["customer_name"] == "Lookbook Patel"


async def test_request_keeps_snapshot_if_retail_moves(owner_client: AsyncClient) -> None:
    sku = await _retail_sku(owner_client, "LB-RQ-SNAP", retail="1000.00")
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Snap request", "price_mode": "retail", "sku_ids": [sku["id"]]},
    )
    assert created.status_code == 201
    patched = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}", json={"retail_ex_vat": "2000.00"}
    )
    assert patched.status_code == 200, patched.text
    requested = await owner_client.post(
        f"/api/v1/public/lookbooks/{created.json()['token']}/request",
        json={"name": "Sam", "contact": "sam@example.com", "sku_ids": [sku["id"]]},
    )
    assert requested.status_code == 204
    activity = await owner_client.get(f"/api/v1/lookbooks/{created.json()['id']}/activity")
    quote = await owner_client.get(f"/api/v1/quotes/{activity.json()['quotes'][0]['id']}")
    assert quote.json()["lines"][0]["unit_ex_vat"] == "1000.00"


async def test_hidden_and_foreign_request_rejected(owner_client: AsyncClient) -> None:
    sku = await _retail_sku(owner_client, "LB-RQ-HID")
    hidden = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Hidden request", "price_mode": "hidden", "sku_ids": [sku["id"]]},
    )
    assert hidden.status_code == 201
    denied = await owner_client.post(
        f"/api/v1/public/lookbooks/{hidden.json()['token']}/request",
        json={"name": "Ada", "contact": "0831112222", "sku_ids": [sku["id"]]},
    )
    assert denied.status_code == 400

    live = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Live request", "price_mode": "retail", "sku_ids": [sku["id"]]},
    )
    assert live.status_code == 201
    foreign = await owner_client.post(
        f"/api/v1/public/lookbooks/{live.json()['token']}/request",
        json={"name": "Ada", "contact": "0831112222", "sku_ids": [str(uuid4())]},
    )
    assert foreign.status_code == 400
