"""Lookbook S4 — first-party events and staff activity."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient

from tests.test_lookbooks import _retail_sku
from tests.test_purchase_orders import _relogin_owner


async def _lookbook(owner_client: AsyncClient, *refs: str) -> dict:
    sku_ids = []
    for ref in refs:
        sku = await _retail_sku(owner_client, ref)
        sku_ids.append(sku["id"])
    created = await owner_client.post(
        "/api/v1/lookbooks",
        json={"name": "Events", "price_mode": "retail", "sku_ids": sku_ids},
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_open_and_dwell_show_in_activity(owner_client: AsyncClient) -> None:
    lookbook = await _lookbook(owner_client, "LB-EV-A", "LB-EV-B")
    token = lookbook["token"]
    linger = lookbook["items"][0]["sku_id"]
    other = lookbook["items"][1]["sku_id"]
    posted = await owner_client.post(
        f"/api/v1/public/lookbooks/{token}/events",
        json={
            "visitor_id": "visitor-aaaa",
            "events": [
                {"event_type": "open"},
                {"event_type": "sku_visible", "sku_id": linger, "duration_ms": 4000},
                {"event_type": "sku_visible", "sku_id": other, "duration_ms": 500},
                {"event_type": "heart", "sku_id": linger},
            ],
        },
    )
    assert posted.status_code == 204, posted.text

    activity = await owner_client.get(f"/api/v1/lookbooks/{lookbook['id']}/activity")
    assert activity.status_code == 200, activity.text
    body = activity.json()
    assert body["opens"] == 1
    assert body["hearts"] == 1
    assert body["submits"] == 0
    assert body["skus"][0]["sku_id"] == linger
    assert body["skus"][0]["dwell_ms"] == 4000
    assert body["skus"][0]["hearts"] == 1


async def test_unheart_nets_activity_hearts(owner_client: AsyncClient) -> None:
    lookbook = await _lookbook(owner_client, "LB-EV-HEART", "LB-EV-UNHEART")
    kept = lookbook["items"][0]["sku_id"]
    dropped = lookbook["items"][1]["sku_id"]
    posted = await owner_client.post(
        f"/api/v1/public/lookbooks/{lookbook['token']}/events",
        json={
            "visitor_id": "visitor-dddd",
            "events": [
                {"event_type": "heart", "sku_id": kept},
                {"event_type": "heart", "sku_id": dropped},
                {"event_type": "unheart", "sku_id": dropped},
            ],
        },
    )
    assert posted.status_code == 204, posted.text
    activity = await owner_client.get(f"/api/v1/lookbooks/{lookbook['id']}/activity")
    assert activity.status_code == 200, activity.text
    body = activity.json()
    assert body["hearts"] == 1
    by_sku = {row["sku_id"]: row for row in body["skus"]}
    assert by_sku[kept]["hearts"] == 1
    assert by_sku[dropped]["hearts"] == 0


async def test_foreign_sku_event_400_and_revoked_404(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    lookbook = await _lookbook(owner_client, "LB-EV-FOR")
    token = lookbook["token"]
    foreign = await owner_client.post(
        f"/api/v1/public/lookbooks/{token}/events",
        json={
            "visitor_id": "visitor-bbbb",
            "events": [{"event_type": "heart", "sku_id": str(uuid4())}],
        },
    )
    assert foreign.status_code == 400

    revoked = await owner_client.post(f"/api/v1/lookbooks/{lookbook['id']}/revoke")
    assert revoked.status_code == 200
    async_client.cookies.clear()
    gone = await async_client.post(
        f"/api/v1/public/lookbooks/{token}/events",
        json={"visitor_id": "visitor-cccc", "events": [{"event_type": "open"}]},
    )
    assert gone.status_code == 404
    await _relogin_owner(owner_client)
