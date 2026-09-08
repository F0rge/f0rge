"""V2-S3 stock adjustments."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


def _sku_payload(suffix: str, **overrides: object) -> dict:
    body: dict = {
        "our_ref": f"ADJ-{suffix}-REF",
        "our_barcode": f"ADJ-{suffix}-BAR",
        "name": f"Adjustment {suffix}",
        "design": f"Adjustment {suffix} design",
        "fabric": f"Adjustment {suffix} fabric",
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


async def _location_on_hand(client: AsyncClient, sku_id: str, location_id: str) -> int:
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


async def _account_balances(client: AsyncClient) -> dict[str, str]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["balance_zar"] for account in resp.json()}


async def test_opening_increase_posts_inventory_and_equity(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "OPEN", location_id, qty=5)
    before = await _account_balances(owner_client)

    created = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "opening"},
    )
    assert created.status_code == 201
    assert created.json()["location_name"] == "Kramerville"
    assert created.json()["status"] == "draft"
    adjustment_id = created.json()["id"]

    line = await owner_client.post(
        f"/api/v1/adjustments/{adjustment_id}/lines",
        json={"sku_id": sku["id"], "qty_delta": 2, "unit_cost_zar": "100.00"},
    )
    assert line.status_code == 201
    assert line.json()["our_ref"] == sku["our_ref"]
    assert line.json()["name"] == sku["name"]
    assert line.json()["current_qty"] == 5
    assert line.json()["new_qty"] == 7

    completed = await owner_client.post(f"/api/v1/adjustments/{adjustment_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert await _location_on_hand(owner_client, sku["id"], location_id) == 7

    after = await _account_balances(owner_client)
    assert after["1300"] == "200.00"
    assert after["3000"] == "-200.00"
    assert Decimal(after["1300"]) > Decimal(before["1300"])
    assert Decimal(after["3000"]) < Decimal(before["3000"])


async def test_damage_decrease_posts_cogs_and_inventory(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "DMG", location_id, qty=5)
    before = await _account_balances(owner_client)

    created = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "damage"},
    )
    assert created.status_code == 201
    adjustment_id = created.json()["id"]

    line = await owner_client.post(
        f"/api/v1/adjustments/{adjustment_id}/lines",
        json={"sku_id": sku["id"], "qty_delta": -2},
    )
    assert line.status_code == 201

    completed = await owner_client.post(f"/api/v1/adjustments/{adjustment_id}/complete")
    assert completed.status_code == 200
    assert await _location_on_hand(owner_client, sku["id"], location_id) == 3

    after = await _account_balances(owner_client)
    assert after["5000"] == "200.00"
    assert after["1300"] == "-200.00"
    assert Decimal(after["5000"]) > Decimal(before["5000"])
    assert Decimal(after["1300"]) < Decimal(before["1300"])


async def test_damage_positive_qty_is_rejected(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "POS", location_id, qty=3)

    created = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "damage"},
    )
    assert created.status_code == 201
    adjustment_id = created.json()["id"]

    line = await owner_client.post(
        f"/api/v1/adjustments/{adjustment_id}/lines",
        json={"sku_id": sku["id"], "qty_delta": 1},
    )
    assert line.status_code == 400


async def test_buyer_cannot_create_warehouse_can(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    location_id = await _kramerville_id(owner_client)
    buyer = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-adj@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    assert buyer.status_code == 201
    warehouse = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "adj-warehouse@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    assert warehouse.status_code == 201

    async_client.cookies.clear()
    login_buyer = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-adj@example.com", "password": "buyer-password"},
    )
    assert login_buyer.status_code == 200
    forbidden = await async_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "count_fix"},
    )
    assert forbidden.status_code == 403

    async_client.cookies.clear()
    login_wh = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "adj-warehouse@example.com", "password": "warehouse-password"},
    )
    assert login_wh.status_code == 200
    allowed = await async_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "count_fix"},
    )
    assert allowed.status_code == 201


async def test_in_progress_stocktake_blocks_create(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    await _create_sku_with_opening(owner_client, "LOCK", location_id, qty=2)

    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert started.status_code == 201

    created = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "count_fix"},
    )
    assert created.status_code == 409
    assert created.json()["detail"] == "Location is locked for stocktake"


async def test_cancel_draft_leaves_stock_and_books_unchanged(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "CAN", location_id, qty=6)
    before_qty = await _location_on_hand(owner_client, sku["id"], location_id)
    before_balances = await _account_balances(owner_client)

    created = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "theft"},
    )
    assert created.status_code == 201
    adjustment_id = created.json()["id"]

    line = await owner_client.post(
        f"/api/v1/adjustments/{adjustment_id}/lines",
        json={"sku_id": sku["id"], "qty_delta": -1},
    )
    assert line.status_code == 201

    cancelled = await owner_client.post(f"/api/v1/adjustments/{adjustment_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert await _location_on_hand(owner_client, sku["id"], location_id) == before_qty
    assert await _account_balances(owner_client) == before_balances


async def test_complete_with_no_lines_is_rejected(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    created = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "write_off"},
    )
    assert created.status_code == 201

    completed = await owner_client.post(f"/api/v1/adjustments/{created.json()['id']}/complete")
    assert completed.status_code == 400
