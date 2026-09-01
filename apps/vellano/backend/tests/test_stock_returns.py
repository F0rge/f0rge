"""V2-S5 stock returns / RMA tests."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import (
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_till import (
    _inventory_on_hand,
    _set_retail_price,
)
from tests.test_transfers import _receive_qty_at_location


async def _login_till(client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-po@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    if create_user.status_code not in (201, 409):
        assert create_user.status_code == 201

    client.cookies.clear()
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "till-po@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200
    return client


async def _create_till_user(async_client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-s5-rtn@example.com",
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
        json={"email": "till-s5-rtn@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _create_buyer_user(async_client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-s5-rtn@example.com",
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
        json={"email": "buyer-s5-rtn@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _till_sale(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
) -> tuple[str, str, str, dict]:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref=our_ref,
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 2)

    till = await _login_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201
    body = sale.json()
    await _relogin_owner(owner_client)
    return sku_id, bedford_id, body["invoice_id"], body


def _return_payload(
    invoice_id: str,
    location_id: str,
    invoice_line_id: str,
    disposition: str,
) -> dict:
    return {
        "invoice_id": invoice_id,
        "location_id": location_id,
        "reason": "damaged",
        "disposition": disposition,
        "lines": [{"invoice_line_id": invoice_line_id, "qty": 1}],
    }


async def _login_warehouse(client: AsyncClient) -> AsyncClient:
    client.cookies.clear()
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-po@example.com", "password": "warehouse-password"},
    )
    assert login_resp.status_code == 200
    return client


async def _transfer_to_bedfordview(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    sku_id: str,
    qty: int,
) -> str:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _login_warehouse(async_client)
    await _relogin_owner(owner_client)
    transfer = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": kramerville_id,
            "to_location_id": bedford_id,
            "sku_id": sku_id,
            "qty": qty,
        },
    )
    assert transfer.status_code == 200
    return bedford_id


async def test_till_restock_return_restores_on_hand_and_creates_cn(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id, invoice_id, sale = await _till_sale(
        async_client,
        owner_client,
        "RTN-RESTOCK",
    )
    invoice_line_id = sale["lines"][0]["id"]

    before = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert before == 1

    created = await owner_client.post(
        "/api/v1/returns",
        json=_return_payload(invoice_id, bedford_id, invoice_line_id, "restock"),
    )
    assert created.status_code == 201
    return_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    completed = await owner_client.post(f"/api/v1/returns/{return_id}/complete")
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "completed"
    assert body["credit_note_id"] is not None

    after = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert after == 2

    credit_notes = await owner_client.get("/api/v1/credit-notes")
    assert credit_notes.status_code == 200
    assert any(cn["id"] == body["credit_note_id"] for cn in credit_notes.json())


async def test_till_write_off_keeps_stock_decremented_but_creates_cn(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id, invoice_id, sale = await _till_sale(
        async_client,
        owner_client,
        "RTN-WRITEOFF",
    )
    invoice_line_id = sale["lines"][0]["id"]

    before = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert before == 1

    created = await owner_client.post(
        "/api/v1/returns",
        json=_return_payload(invoice_id, bedford_id, invoice_line_id, "write_off"),
    )
    assert created.status_code == 201
    return_id = created.json()["id"]

    completed = await owner_client.post(f"/api/v1/returns/{return_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["credit_note_id"] is not None

    after = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert after == 1


async def test_second_return_for_same_invoice_conflicts(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, sale = await _till_sale(
        async_client,
        owner_client,
        "RTN-DUP",
    )
    invoice_line_id = sale["lines"][0]["id"]
    payload = _return_payload(invoice_id, bedford_id, invoice_line_id, "write_off")

    first = await owner_client.post("/api/v1/returns", json=payload)
    assert first.status_code == 201

    second = await owner_client.post("/api/v1/returns", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "This invoice already has a return"


async def test_return_after_full_credit_note_conflicts(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, sale = await _till_sale(
        async_client,
        owner_client,
        "RTN-CN",
    )
    invoice_line_id = sale["lines"][0]["id"]

    cn = await owner_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice_id},
    )
    assert cn.status_code == 201

    created = await owner_client.post(
        "/api/v1/returns",
        json=_return_payload(invoice_id, bedford_id, invoice_line_id, "write_off"),
    )
    assert created.status_code == 409
    assert created.json()["detail"] == "This invoice has already been credited"


async def test_books_invoice_restock_rejected_write_off_allowed(
    owner_client: AsyncClient,
) -> None:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Books Return Customer"},
    )
    assert customer_resp.status_code == 201
    invoice_resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Consulting", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()
    invoice_line_id = invoice["lines"][0]["id"]
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")

    restock = await owner_client.post(
        "/api/v1/returns",
        json=_return_payload(invoice["id"], bedford_id, invoice_line_id, "restock"),
    )
    assert restock.status_code == 400
    assert restock.json()["detail"] == "Restock is only available for till sales"

    created = await owner_client.post(
        "/api/v1/returns",
        json=_return_payload(invoice["id"], bedford_id, invoice_line_id, "write_off"),
    )
    assert created.status_code == 201
    return_id = created.json()["id"]

    completed = await owner_client.post(f"/api/v1/returns/{return_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["credit_note_id"] is not None


async def test_buyer_cannot_create_return_till_can(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, sale = await _till_sale(
        async_client,
        owner_client,
        "RTN-ROLE",
    )
    invoice_line_id = sale["lines"][0]["id"]
    payload = _return_payload(invoice_id, bedford_id, invoice_line_id, "write_off")

    buyer = await _create_buyer_user(async_client, owner_client)
    forbidden = await buyer.post("/api/v1/returns", json=payload)
    assert forbidden.status_code == 403

    till = await _create_till_user(async_client, owner_client)
    allowed = await till.post("/api/v1/returns", json=payload)
    assert allowed.status_code == 201


async def test_restock_complete_blocked_during_stocktake(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id, invoice_id, sale = await _till_sale(
        async_client,
        owner_client,
        "RTN-LOCK",
    )
    invoice_line_id = sale["lines"][0]["id"]

    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": bedford_id})
    assert started.status_code == 201

    created = await owner_client.post(
        "/api/v1/returns",
        json=_return_payload(invoice_id, bedford_id, invoice_line_id, "restock"),
    )
    assert created.status_code == 201
    return_id = created.json()["id"]

    completed = await owner_client.post(f"/api/v1/returns/{return_id}/complete")
    assert completed.status_code == 409
    assert completed.json()["detail"] == "Location is locked for stocktake"


async def test_cancel_draft_allows_new_return(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, sale = await _till_sale(
        async_client,
        owner_client,
        "RTN-CANCEL",
    )
    invoice_line_id = sale["lines"][0]["id"]
    payload = _return_payload(invoice_id, bedford_id, invoice_line_id, "write_off")

    created = await owner_client.post("/api/v1/returns", json=payload)
    assert created.status_code == 201
    return_id = created.json()["id"]

    cancelled = await owner_client.post(f"/api/v1/returns/{return_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["credit_note_id"] is None

    again = await owner_client.post("/api/v1/returns", json=payload)
    assert again.status_code == 201
