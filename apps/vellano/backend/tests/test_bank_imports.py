"""S7 bank import and reconciliation tests."""

from __future__ import annotations


from httpx import AsyncClient


SAMPLE_CSV = """Date,Description,Reference,Amount
2026-09-02,Customer payment INV-0001,REF001,1150.00
2026-09-03,Supplier payment BILL-0001,REF002,-1800.00
2026-09-04,Unmatched deposit,REF003,500.00
"""


async def _create_customer_invoice(owner_client: AsyncClient) -> dict:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Bank Customer"},
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
        json={"name": "Bank Supplier", "default_currency": "USD"},
    )
    assert supplier_resp.status_code == 201
    resp = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier_resp.json()["id"],
            "supplier_ref": "BANK-1",
            "issue_date": "2026-09-01",
            "currency": "USD",
            "fx_to_zar": "18.00",
            "lines": [{"description": "Factory invoice", "qty": 1, "unit_amount": "100.00"}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_unauthenticated_bank_import_returns_401(async_client: AsyncClient) -> None:
    files = {"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")}
    resp = await async_client.post("/api/v1/bank-imports", files=files)
    assert resp.status_code == 401


async def test_upload_bank_csv_creates_three_lines(owner_client: AsyncClient) -> None:
    files = {"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")}
    resp = await owner_client.post("/api/v1/bank-imports", files=files)
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "bank.csv"
    assert body["line_count"] == 3
    assert len(body["lines"]) == 3
    assert body["lines"][0]["amount_zar"] == "1150.00"
    assert body["lines"][2]["matched_payment_id"] is None


async def test_match_marks_payment_reconciled(owner_client: AsyncClient) -> None:
    invoice = await _create_customer_invoice(owner_client)
    payment_resp = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice["id"],
            "amount": "1150.00",
            "currency": "ZAR",
            "paid_on": "2026-09-02",
        },
    )
    assert payment_resp.status_code == 201
    payment = payment_resp.json()
    assert payment["is_reconciled"] is False

    files = {"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")}
    import_resp = await owner_client.post("/api/v1/bank-imports", files=files)
    assert import_resp.status_code == 201
    import_body = import_resp.json()
    line_id = import_body["lines"][0]["id"]
    import_id = import_body["id"]

    match_resp = await owner_client.post(
        f"/api/v1/bank-imports/{import_id}/lines/{line_id}/match",
        json={"payment_id": payment["id"]},
    )
    assert match_resp.status_code == 200
    assert match_resp.json()["matched_payment_id"] == payment["id"]

    payments_resp = await owner_client.get("/api/v1/payments")
    assert payments_resp.status_code == 200
    matched = next(p for p in payments_resp.json() if p["id"] == payment["id"])
    assert matched["is_reconciled"] is True
    assert matched["reconciled_at"] is not None


async def test_books_can_upload_bank_csv(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "books-bank@example.com",
            "password": "books-password",
            "role": "books",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books-bank@example.com", "password": "books-password"},
    )
    assert login_resp.status_code == 200

    files = {"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")}
    resp = await async_client.post("/api/v1/bank-imports", files=files)
    assert resp.status_code == 201


async def test_till_cannot_upload_bank_csv(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-bank@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-bank@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    files = {"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")}
    resp = await async_client.post("/api/v1/bank-imports", files=files)
    assert resp.status_code == 403


async def test_debit_credit_csv_format(owner_client: AsyncClient) -> None:
    csv_content = """Transaction Date,Description,Debit,Credit
2026-09-05,Test debit,100.00,
2026-09-06,Test credit,,200.00
"""
    files = {"file": ("debit-credit.csv", csv_content.encode(), "text/csv")}
    resp = await owner_client.post("/api/v1/bank-imports", files=files)
    assert resp.status_code == 201
    lines = resp.json()["lines"]
    assert lines[0]["amount_zar"] == "-100.00"
    assert lines[1]["amount_zar"] == "200.00"
