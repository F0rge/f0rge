"""S6 payment tests including FX gain/loss."""

from __future__ import annotations

from httpx import AsyncClient


async def _account_balances(owner_client: AsyncClient) -> dict[str, str]:
    resp = await owner_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {a["code"]: a["balance_zar"] for a in resp.json()}


async def _create_customer_invoice(owner_client: AsyncClient) -> dict:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Pay Customer"},
    )
    assert customer_resp.status_code == 201
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_usd_bill(owner_client: AsyncClient) -> dict:
    supplier_resp = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "FX Supplier", "default_currency": "USD"},
    )
    assert supplier_resp.status_code == 201
    resp = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier_resp.json()["id"],
            "supplier_ref": "FX-1",
            "issue_date": "2026-09-01",
            "currency": "USD",
            "fx_to_zar": "18.00",
            "lines": [{"description": "Factory invoice", "qty": 1, "unit_amount": "100.00"}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_payment_in_clears_ar(owner_client: AsyncClient) -> None:
    invoice = await _create_customer_invoice(owner_client)
    resp = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice["id"],
            "amount": "1150.00",
            "currency": "ZAR",
            "paid_on": "2026-09-02",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["payment_number"] == "PAY-0001"
    assert resp.json()["fx_gain_loss_zar"] == "0.00"

    balances = await _account_balances(owner_client)
    assert balances["1200"] == "0.00"
    assert balances["1100"] == "1150.00"


async def test_books_can_create_payment(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    invoice = await _create_customer_invoice(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "books-pay@example.com",
            "password": "books-password",
            "role": "books",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books-pay@example.com", "password": "books-password"},
    )
    assert login_resp.status_code == 200

    resp = await async_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice["id"],
            "amount": "1150.00",
            "currency": "ZAR",
            "paid_on": "2026-09-02",
        },
    )
    assert resp.status_code == 201


async def test_payment_out_fx_loss(owner_client: AsyncClient) -> None:
    bill = await _create_usd_bill(owner_client)
    balances = await _account_balances(owner_client)
    assert balances["1300"] == "1800.00"
    assert balances["2100"] == "-1800.00"

    resp = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "out",
            "bill_id": bill["id"],
            "amount": "100.00",
            "currency": "USD",
            "fx_to_zar": "19.00",
            "paid_on": "2026-09-03",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount_zar"] == "1900.00"
    assert body["fx_gain_loss_zar"] == "-100.00"

    balances = await _account_balances(owner_client)
    assert balances["2100"] == "0.00"
    assert balances["1100"] == "-1900.00"
    assert balances["6100"] == "100.00"


async def test_payment_out_fx_gain(owner_client: AsyncClient) -> None:
    bill = await _create_usd_bill(owner_client)
    resp = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "out",
            "bill_id": bill["id"],
            "amount": "100.00",
            "currency": "USD",
            "fx_to_zar": "17.00",
            "paid_on": "2026-09-04",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount_zar"] == "1700.00"
    assert body["fx_gain_loss_zar"] == "100.00"

    balances = await _account_balances(owner_client)
    assert balances["2100"] == "0.00"
    assert balances["1100"] == "-1700.00"
    assert balances["6100"] == "-100.00"
