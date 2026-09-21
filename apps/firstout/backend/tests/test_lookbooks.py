"""Lookbook S1 — snapshot prices, optional CRM customer, public token + photo."""

from __future__ import annotations

import datetime
from uuid import uuid4

from httpx import AsyncClient

from app.config import settings
from app.services import lookbooks as lookbooks_mod
from tests.test_quotes import _named_customer
from tests.test_sku_bom import _sku
from tests.test_skus import TINY_PNG
from tests.test_purchase_orders import _relogin_owner


async def _retail_sku(owner_client: AsyncClient, our_ref: str, retail: str = "1000.00") -> dict:
    return await _sku(owner_client, our_ref, retail_ex_vat=retail)


async def test_create_walk_in_lookbook_and_public_get(
    owner_client: AsyncClient,
) -> None:
    sku = await _retail_sku(owner_client, "LB-WALK")
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "Sofas — walk-in",
            "price_mode": "retail",
            "sku_ids": [sku["id"]],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["customer_id"] is None
    assert body["customer_name"] is None
    assert body["token"]
    assert body["items"][0]["unit_inc_vat"] == "1150.00"

    public = await owner_client.get(f"/api/v1/public/lookbooks/{body['token']}")
    assert public.status_code == 200, public.text
    payload = public.json()
    assert payload["name"] == "Sofas — walk-in"
    assert payload["company_name"]
    assert len(payload["items"]) == 1
    assert payload["items"][0]["sku_id"] == sku["id"]
    assert payload["items"][0]["unit_inc_vat"] == "1150.00"
    assert payload["items"][0]["name"] == sku["name"]
    dumped = public.text
    assert "cost" not in dumped
    assert "wholesale" not in dumped
    assert "landed" not in dumped
    assert "created_by" not in dumped


async def test_create_lookbook_linked_to_crm_customer(owner_client: AsyncClient) -> None:
    customer_id = await _named_customer(owner_client, "Lookbook CRM")
    sku = await _retail_sku(owner_client, "LB-CRM")
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "Sofas — Patel",
            "customer_id": customer_id,
            "price_mode": "retail",
            "sku_ids": [sku["id"]],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["customer_id"] == customer_id
    assert body["customer_name"] == "Lookbook CRM"


async def test_invalid_customer_id_404(owner_client: AsyncClient) -> None:
    sku = await _retail_sku(owner_client, "LB-BADCUST")
    resp = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "Bad customer",
            "customer_id": str(uuid4()),
            "price_mode": "retail",
            "sku_ids": [sku["id"]],
        },
    )
    assert resp.status_code == 404


async def test_unknown_expired_revoked_tokens_404(
    owner_client: AsyncClient,
    monkeypatch,
) -> None:
    unknown = await owner_client.get("/api/v1/public/lookbooks/not-a-real-token")
    assert unknown.status_code == 404

    sku = await _retail_sku(owner_client, "LB-EXPIRE")
    frozen = datetime.datetime(2026, 1, 1, 12, 0, 0)
    monkeypatch.setattr(lookbooks_mod, "_utcnow", lambda: frozen)
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "Expires",
            "price_mode": "retail",
            "sku_ids": [sku["id"]],
            "expires_in_days": 1,
        },
    )
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    lookbook_id = created.json()["id"]

    monkeypatch.setattr(lookbooks_mod, "_utcnow", lambda: frozen + datetime.timedelta(days=2))
    expired = await owner_client.get(f"/api/v1/public/lookbooks/{token}")
    assert expired.status_code == 404

    monkeypatch.setattr(lookbooks_mod, "_utcnow", lambda: frozen)
    sku2 = await _retail_sku(owner_client, "LB-REVOKE")
    live = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Revoke me", "price_mode": "retail", "sku_ids": [sku2["id"]]},
    )
    assert live.status_code == 201, live.text
    live_token = live.json()["token"]
    revoked = await owner_client.post(f"/api/v1/lookbooks/{live.json()['id']}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    gone = await owner_client.get(f"/api/v1/public/lookbooks/{live_token}")
    assert gone.status_code == 404
    still_listed = await owner_client.get(f"/api/v1/lookbooks/{lookbook_id}")
    assert still_listed.status_code == 200


async def test_price_list_and_hidden_snapshots(owner_client: AsyncClient) -> None:
    sku = await _retail_sku(owner_client, "LB-LIST", retail="1000.00")
    listed = await owner_client.post("/api/v1/price-lists", json={"name": "Lookbook trade"})
    assert listed.status_code == 201, listed.text
    price_list_id = listed.json()["id"]
    item = await owner_client.put(
        f"/api/v1/price-lists/{price_list_id}/items",
        json={"sku_id": sku["id"], "unit_ex_vat": "800.00"},
    )
    assert item.status_code == 200, item.text

    trade = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "Trade sofas",
            "price_mode": "price_list",
            "price_list_id": price_list_id,
            "sku_ids": [sku["id"]],
        },
    )
    assert trade.status_code == 201, trade.text
    assert trade.json()["items"][0]["unit_inc_vat"] == "920.00"

    hidden = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "No prices",
            "price_mode": "hidden",
            "sku_ids": [sku["id"]],
        },
    )
    assert hidden.status_code == 201, hidden.text
    assert hidden.json()["items"][0]["unit_inc_vat"] is None
    public = await owner_client.get(f"/api/v1/public/lookbooks/{hidden.json()['token']}")
    assert public.json()["items"][0]["unit_inc_vat"] is None


async def test_public_photo_without_staff_cookie(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    sku = await _retail_sku(owner_client, "LB-PHOTO")
    photo = await owner_client.post(
        f"/api/v1/skus/{sku['id']}/photo",
        files={"photo": ("sku.png", TINY_PNG, "image/png")},
    )
    assert photo.status_code == 200, photo.text
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Photos", "price_mode": "retail", "sku_ids": [sku["id"]]},
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["items"][0]["id"]
    token = created.json()["token"]
    public = await owner_client.get(f"/api/v1/public/lookbooks/{token}")
    assert public.json()["items"][0]["photo_path"] == (
        f"/api/v1/public/lookbooks/{token}/items/{item_id}/photo"
    )

    async_client.cookies.clear()
    photo_resp = await async_client.get(f"/api/v1/public/lookbooks/{token}/items/{item_id}/photo")
    assert photo_resp.status_code == 200
    assert photo_resp.headers["content-type"].startswith("image/jpeg")
    await _relogin_owner(owner_client)


async def test_till_can_create_lookbook_buyer_cannot(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _retail_sku(owner_client, "LB-RBAC")
    payload = {"name": "RBAC", "price_mode": "retail", "sku_ids": [sku["id"]]}

    async_client.cookies.clear()
    till_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till@example.com", "password": settings.seed_till_password},
    )
    assert till_login.status_code == 200
    till_create = await async_client.post("/api/v1/lookbooks", json=payload)
    assert till_create.status_code == 201, till_create.text

    async_client.cookies.clear()
    buyer_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer@example.com", "password": settings.seed_buyer_password},
    )
    assert buyer_login.status_code == 200
    buyer_create = await async_client.post("/api/v1/lookbooks", json=payload)
    assert buyer_create.status_code == 403
    await _relogin_owner(owner_client)


async def test_list_includes_walk_in_and_crm_rows(owner_client: AsyncClient) -> None:
    sku = await _retail_sku(owner_client, "LB-LISTROW")
    customer_id = await _named_customer(owner_client, "List CRM")
    walk = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Walk row", "price_mode": "retail", "sku_ids": [sku["id"]]},
    )
    crm = await owner_client.post(
        "/api/v1/lookbooks",
        json={
            "name": "CRM row",
            "customer_id": customer_id,
            "price_mode": "retail",
            "sku_ids": [sku["id"]],
        },
    )
    assert walk.status_code == 201
    assert crm.status_code == 201
    listed = await owner_client.get("/api/v1/lookbooks")
    assert listed.status_code == 200
    names = {row["name"] for row in listed.json()["items"]}
    assert "Walk row" in names
    assert "CRM row" in names
