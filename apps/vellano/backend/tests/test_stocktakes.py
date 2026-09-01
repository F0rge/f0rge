"""S2 stocktake by location."""

from __future__ import annotations

from httpx import AsyncClient


def _sku_payload(suffix: str, **overrides: object) -> dict:
    body: dict = {
        "our_ref": f"STK-{suffix}-REF",
        "our_barcode": f"STK-{suffix}-BAR",
        "name": f"Stocktake {suffix}",
        "design": f"Stocktake {suffix} design",
        "fabric": f"Stocktake {suffix} fabric",
    }
    body.update(overrides)
    return body


async def _kramerville_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    for loc in resp.json():
        if loc["name"] == "Kramerville":
            return loc["id"]
    raise AssertionError("Kramerville not found")


async def _location_on_hand(
    client: AsyncClient,
    sku_id: str,
    location_id: str,
) -> int:
    inv = await client.get("/api/v1/inventory")
    assert inv.status_code == 200
    row = next(item for item in inv.json() if item["sku_id"] == sku_id)
    loc = next(item for item in row["locations"] if item["location_id"] == location_id)
    return loc["on_hand"]


async def _create_sku_with_opening(
    client: AsyncClient,
    suffix: str,
    location_id: str,
    qty: int = 5,
) -> dict:
    resp = await client.post(
        "/api/v1/skus",
        json=_sku_payload(
            suffix,
            opening_location_id=location_id,
            opening_qty=qty,
            opening_unit_cost_zar="100.00",
        ),
    )
    assert resp.status_code == 201
    return resp.json()


def _line_for_sku(body: dict, sku_id: str) -> dict:
    return next(line for line in body["lines"] if line["sku_id"] == sku_id)


async def test_start_stocktake_snapshots_opening_on_hand(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "SNAP", location_id, qty=5)

    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert started.status_code == 201
    body = started.json()
    assert body["location_id"] == location_id
    assert body["status"] == "in_progress"
    line = _line_for_sku(body, sku["id"])
    assert line["expected_qty"] == 5
    assert line["our_ref"] == sku["our_ref"]
    assert line["counted_qty"] is None
    assert line["variance"] is None


async def test_complete_adjusts_on_hand_and_releases_lock(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "DONE", location_id, qty=5)

    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert started.status_code == 201
    stocktake_id = started.json()["id"]
    line = _line_for_sku(started.json(), sku["id"])

    patched = await owner_client.patch(
        f"/api/v1/stocktakes/{stocktake_id}/lines/{line['id']}",
        json={"counted_qty": 3},
    )
    assert patched.status_code == 200
    assert patched.json()["sku_id"] == sku["id"]
    assert patched.json()["variance"] == -2

    completed = await owner_client.post(f"/api/v1/stocktakes/{stocktake_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert await _location_on_hand(owner_client, sku["id"], location_id) == 3

    second = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert second.status_code == 201
    assert second.json()["status"] == "in_progress"


async def test_second_start_while_in_progress_returns_409(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    await _create_sku_with_opening(owner_client, "LOCK", location_id, qty=2)

    first = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert first.status_code == 201

    second = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert second.status_code == 409
    assert second.json()["detail"] == "Location is locked for stocktake"


async def test_transfer_from_locked_location_returns_409(owner_client: AsyncClient) -> None:
    from_loc = await owner_client.post(
        "/api/v1/locations",
        json={"name": "STK Lock From", "type": "warehouse"},
    )
    to_loc = await owner_client.post(
        "/api/v1/locations",
        json={"name": "STK Lock To", "type": "warehouse"},
    )
    assert from_loc.status_code == 201
    assert to_loc.status_code == 201
    from_id = from_loc.json()["id"]
    to_id = to_loc.json()["id"]

    sku = await _create_sku_with_opening(owner_client, "XFER", from_id, qty=4)
    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": from_id})
    assert started.status_code == 201

    transfer = await owner_client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": from_id,
            "to_location_id": to_id,
            "sku_id": sku["id"],
            "qty": 1,
        },
    )
    assert transfer.status_code == 409
    assert transfer.json()["detail"] == "Location is locked for stocktake"


async def test_lookup_by_our_barcode_returns_line(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "BAR", location_id, qty=1)

    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert started.status_code == 201
    stocktake_id = started.json()["id"]
    expected_line = _line_for_sku(started.json(), sku["id"])

    lookup = await owner_client.post(
        f"/api/v1/stocktakes/{stocktake_id}/lookup",
        json={"barcode": sku["our_barcode"]},
    )
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["id"] == expected_line["id"]
    assert body["sku_id"] == sku["id"]
    assert body["our_barcode"] == sku["our_barcode"]


async def test_till_role_cannot_start_stocktake(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    location_id = await _kramerville_id(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-stocktakes@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-stocktakes@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    started = await async_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert started.status_code == 403


async def test_cancel_unlocks_without_changing_qty(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "CAN", location_id, qty=6)

    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert started.status_code == 201
    stocktake_id = started.json()["id"]
    line = _line_for_sku(started.json(), sku["id"])

    patched = await owner_client.patch(
        f"/api/v1/stocktakes/{stocktake_id}/lines/{line['id']}",
        json={"counted_qty": 1},
    )
    assert patched.status_code == 200

    cancelled = await owner_client.post(f"/api/v1/stocktakes/{stocktake_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert await _location_on_hand(owner_client, sku["id"], location_id) == 6

    second = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert second.status_code == 201
