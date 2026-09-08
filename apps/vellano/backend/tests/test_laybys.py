"""V2-S6 layby tests."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.test_ledger_accounts import _account_balance
from tests.test_purchase_orders import _relogin_owner
from tests.test_till import _inventory_on_hand, _set_retail_price, _transfer_to_bedfordview
from tests.test_transfers import _receive_qty_at_location


async def _create_customer(owner_client: AsyncClient) -> str:
    resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Layby Customer"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_till_user(async_client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-s6-lb@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    if create_user.status_code == 409:
        pass
    else:
        assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-s6-lb@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _create_buyer_user(async_client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-s6-lb@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    if create_user.status_code == 409:
        pass
    else:
        assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-s6-lb@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _stocked_sku_at_bedford(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
    qty: int = 2,
) -> tuple[str, str]:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=qty,
        location_name="Kramerville",
        our_ref=our_ref,
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, qty)
    return sku_id, bedford_id


def _layby_payload(
    customer_id: str,
    location_id: str,
    sku_id: str,
    *,
    hold_stock: bool = True,
    deposit: str = "500.00",
) -> dict:
    return {
        "customer_id": customer_id,
        "location_id": location_id,
        "due_date": "2026-12-01",
        "hold_stock": hold_stock,
        "deposit_amount": deposit,
        "tender": "cash",
        "lines": [{"sku_id": sku_id, "qty": 1}],
    }


async def test_create_hold_stock_decreases_on_hand_and_posts_deposit(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "LB-HOLD",
    )
    customer_id = await _create_customer(owner_client)
    deposits_before = Decimal(await _account_balance(owner_client, "2300"))

    before = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert before == 2

    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id, deposit="500.00"),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "open"
    assert body["amount_paid"] == "500.00"
    assert body["total_inc_vat"] == "1150.00"
    assert body["balance"] == "650.00"

    after = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert after == 1

    deposits_after = Decimal(await _account_balance(owner_client, "2300"))
    assert deposits_after == deposits_before - Decimal("500.00")


async def test_payment_to_ready_then_complete(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "LB-COMPLETE",
    )
    customer_id = await _create_customer(owner_client)
    deposits_before = Decimal(await _account_balance(owner_client, "2300"))
    sales_before = Decimal(await _account_balance(owner_client, "4000"))
    vat_before = Decimal(await _account_balance(owner_client, "2200"))

    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id, deposit="500.00"),
    )
    assert created.status_code == 201
    layby_id = created.json()["id"]

    paid = await till.post(
        f"/api/v1/laybys/{layby_id}/payments",
        json={"amount": "650.00", "tender": "card"},
    )
    assert paid.status_code == 201
    assert paid.json()["status"] == "ready"
    assert paid.json()["amount_paid"] == "1150.00"

    on_hand_before_complete = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert on_hand_before_complete == 1

    completed = await till.post(f"/api/v1/laybys/{layby_id}/complete")
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "completed"
    assert body["invoice_id"] is not None

    on_hand_after = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert on_hand_after == 1

    deposits_after = Decimal(await _account_balance(owner_client, "2300"))
    assert deposits_after == deposits_before

    sales_after = Decimal(await _account_balance(owner_client, "4000"))
    vat_after = Decimal(await _account_balance(owner_client, "2200"))
    assert sales_after - sales_before == Decimal("-1000.00")
    assert vat_after - vat_before == Decimal("-150.00")


async def test_no_hold_stock_decrements_on_complete(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "LB-NOHOLD",
    )
    customer_id = await _create_customer(owner_client)

    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(
            customer_id,
            bedford_id,
            sku_id,
            hold_stock=False,
            deposit="1150.00",
        ),
    )
    assert created.status_code == 201
    layby_id = created.json()["id"]
    assert created.json()["status"] == "ready"

    before = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert before == 2

    completed = await till.post(f"/api/v1/laybys/{layby_id}/complete")
    assert completed.status_code == 200

    after = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert after == 1


async def test_cancel_held_layby_restores_stock_and_reverses_deposits(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "LB-CANCEL",
    )
    customer_id = await _create_customer(owner_client)
    deposits_before = Decimal(await _account_balance(owner_client, "2300"))

    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id, deposit="500.00"),
    )
    assert created.status_code == 201
    layby_id = created.json()["id"]

    cancelled = await till.post(f"/api/v1/laybys/{layby_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    after = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert after == 2

    deposits_after = Decimal(await _account_balance(owner_client, "2300"))
    assert deposits_after == deposits_before


async def test_buyer_forbidden_till_allowed(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "LB-ROLE",
    )
    customer_id = await _create_customer(owner_client)
    payload = _layby_payload(customer_id, bedford_id, sku_id)

    buyer = await _create_buyer_user(async_client, owner_client)
    forbidden = await buyer.post("/api/v1/laybys", json=payload)
    assert forbidden.status_code == 403

    till = await _create_till_user(async_client, owner_client)
    allowed = await till.post("/api/v1/laybys", json=payload)
    assert allowed.status_code == 201


async def test_hold_blocked_during_stocktake(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "LB-LOCK",
    )
    customer_id = await _create_customer(owner_client)

    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": bedford_id})
    assert started.status_code == 201

    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id),
    )
    assert created.status_code == 409
    assert created.json()["detail"] == "Location is locked for stocktake"


async def test_deposit_over_total_rejected_and_complete_while_open_conflicts(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "LB-VALID",
    )
    customer_id = await _create_customer(owner_client)

    till = await _create_till_user(async_client, owner_client)
    over = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id, deposit="1200.00"),
    )
    assert over.status_code == 400
    assert over.json()["detail"] == "Deposit cannot exceed layby total"

    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id, deposit="500.00"),
    )
    assert created.status_code == 201
    layby_id = created.json()["id"]

    complete = await till.post(f"/api/v1/laybys/{layby_id}/complete")
    assert complete.status_code == 409
    assert complete.json()["detail"] == "Layby is not ready to complete"
