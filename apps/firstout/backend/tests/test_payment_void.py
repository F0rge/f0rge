"""Payment method/reference, voiding, open documents and the payments workspace."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.journal import JournalDocumentType, JournalEntry, JournalStatus
from app.models.payment import Payment
from tests.conftest import authenticate_as, create_test_staff

TODAY = date.today().isoformat()


async def _balances(client: AsyncClient) -> dict[str, str]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["balance_zar"] for account in resp.json()}


async def _invoice(client: AsyncClient, name: str) -> dict:
    customer = await client.post("/api/v1/customers", json={"name": name})
    assert customer.status_code == 201
    resp = await client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": TODAY,
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _usd_bill(client: AsyncClient, name: str) -> dict:
    supplier = await client.post(
        "/api/v1/suppliers", json={"name": name, "default_currency": "USD"}
    )
    assert supplier.status_code == 201
    resp = await client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier.json()["id"],
            "supplier_ref": "VOID-FX",
            "issue_date": TODAY,
            "currency": "USD",
            "fx_to_zar": "18.00",
            "lines": [{"description": "Factory invoice", "qty": 1, "unit_amount": "100.00"}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _pay_in(client: AsyncClient, invoice_id: str, amount: str, **extra) -> object:
    return await client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice_id,
            "amount": amount,
            "currency": "ZAR",
            "paid_on": TODAY,
            **extra,
        },
    )


async def _void(client: AsyncClient, payment_id: str, reason: str = "EFT bounced") -> object:
    return await client.post(f"/api/v1/payments/{payment_id}/void", json={"reason": reason})


async def _workspace(client: AsyncClient, **body) -> dict:
    resp = await client.post(
        "/api/v1/record-workspaces/payments/query",
        json={"sort": {"field": "paid_on", "direction": "desc"}, **body},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_payment_records_method_and_reference(owner_client: AsyncClient) -> None:
    invoice = await _invoice(owner_client, "Method Customer")
    resp = await _pay_in(
        owner_client, invoice["id"], "100.00", tender="eft", reference="  FNB 123  "
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tender"] == "eft"
    assert body["reference"] == "FNB 123"
    assert body["party_name"] == "Method Customer"
    assert body["document_number"] == invoice["invoice_number"]
    assert body["is_voided"] is False

    found = await _workspace(
        owner_client,
        q="FNB 123",
        filters=[{"field": "tender", "operator": "eq", "value": "eft"}],
    )
    assert [item["id"] for item in found["items"]] == [body["id"]]

    bad = await _pay_in(owner_client, invoice["id"], "1.00", tender="cheque")
    assert bad.status_code == 422


async def test_payment_over_balance_is_rejected(owner_client: AsyncClient) -> None:
    invoice = await _invoice(owner_client, "Over Customer")
    resp = await _pay_in(owner_client, invoice["id"], "1150.01", tender="cash")
    assert resp.status_code == 400
    assert "still owing" in resp.json()["detail"]


async def test_void_reverses_invoice_balance_and_ledger(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    before = await _balances(owner_client)
    invoice = await _invoice(owner_client, "Void Customer")
    payment = (await _pay_in(owner_client, invoice["id"], "400.00", tender="card")).json()
    summary_before = (await owner_client.get("/api/v1/payments/summary")).json()

    resp = await _void(owner_client, payment["id"], "  Captured twice ")
    assert resp.status_code == 200, resp.text
    voided = resp.json()
    assert voided["is_voided"] is True
    assert voided["void_reason"] == "Captured twice"
    assert voided["voided_at"] is not None

    detail = (await owner_client.get(f"/api/v1/invoices/{invoice['id']}")).json()
    assert detail["amount_paid"] == "0.00"
    assert detail["balance"] == "1150.00"
    assert detail["payment_status"] == "unpaid"

    after = await _balances(owner_client)
    bank_delta = float(after["1100"]) - float(before.get("1100", "0"))
    ar_delta = float(after["1200"]) - float(before.get("1200", "0"))
    assert bank_delta == 0
    assert ar_delta == 1150

    entries = (
        (
            await async_db.execute(
                select(JournalEntry).where(
                    JournalEntry.document_type == JournalDocumentType.PAYMENT,
                    JournalEntry.document_id == UUID(payment["id"]),
                )
            )
        )
        .scalars()
        .all()
    )
    statuses = sorted(entry.status for entry in entries)
    assert statuses == [JournalStatus.POSTED, JournalStatus.VOIDED]
    original = next(entry for entry in entries if entry.status == JournalStatus.VOIDED)
    reversal = next(entry for entry in entries if entry.status == JournalStatus.POSTED)
    assert original.voided_by_id == reversal.id
    assert reversal.source == "void"

    events = await owner_client.get(
        "/api/v1/books-events",
        params={"document_type": "payment", "document_id": payment["id"]},
    )
    assert "voided" in [event["action"] for event in events.json()]

    again = await _void(owner_client, payment["id"])
    assert again.status_code == 400

    active = await _workspace(owner_client, q=invoice["invoice_number"])
    archived = await _workspace(owner_client, q=invoice["invoice_number"], lifecycle="archived")
    assert active["items"] == []
    assert [item["id"] for item in archived["items"]] == [payment["id"]]

    summary = (await owner_client.get("/api/v1/payments/summary")).json()
    assert summary["received_this_month_count"] == summary_before["received_this_month_count"] - 1
    assert (
        float(summary["received_this_month_zar"])
        == float(summary_before["received_this_month_zar"]) - 400
    )

    # The balance is owing again, so the invoice can be paid afresh.
    repaid = await _pay_in(owner_client, invoice["id"], "1150.00", tender="eft")
    assert repaid.status_code == 201


async def test_void_bill_payment_restores_foreign_and_zar_balance(
    owner_client: AsyncClient,
) -> None:
    before = await _balances(owner_client)
    bill = await _usd_bill(owner_client, "Void FX Supplier")
    paid = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "out",
            "bill_id": bill["id"],
            "amount": "40.00",
            "currency": "USD",
            "fx_to_zar": "19.00",
            "paid_on": TODAY,
            "tender": "eft",
            "reference": "SWIFT-1",
        },
    )
    assert paid.status_code == 201, paid.text
    assert paid.json()["fx_gain_loss_zar"] != "0.00"

    resp = await _void(owner_client, paid.json()["id"])
    assert resp.status_code == 200, resp.text

    detail = (await owner_client.get(f"/api/v1/bills/{bill['id']}")).json()
    assert detail["amount_paid_foreign"] == "0.00"
    assert detail["amount_paid_zar"] == "0.00"
    assert detail["balance_foreign"] == "100.00"
    assert detail["payment_status"] == "unpaid"

    after = await _balances(owner_client)
    for code in ("1100", "6100"):
        assert float(after.get(code, "0")) == float(before.get(code, "0"))


async def test_reconciled_payment_cannot_be_voided(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    invoice = await _invoice(owner_client, "Reconciled Customer")
    payment = (await _pay_in(owner_client, invoice["id"], "100.00", tender="eft")).json()
    row = await async_db.get(Payment, UUID(payment["id"]))
    row.is_reconciled = True
    await async_db.flush()

    resp = await _void(owner_client, payment["id"])
    assert resp.status_code == 400
    assert "reconciled" in resp.json()["detail"]
    detail = (await owner_client.get(f"/api/v1/invoices/{invoice['id']}")).json()
    assert detail["amount_paid"] == "100.00"


async def test_void_and_open_documents_need_books_permission_and_a_reason(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    invoice = await _invoice(owner_client, "Permission Customer")
    payment = (await _pay_in(owner_client, invoice["id"], "100.00", tender="cash")).json()

    blank = await _void(owner_client, payment["id"], "   ")
    assert blank.status_code == 422

    await create_test_staff(owner_client, email="till-void@example.com", role="till")
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "till-void@example.com")).status_code == 200
    assert (await _void(async_client, payment["id"])).status_code == 403
    denied = await async_client.get("/api/v1/payments/open-documents", params={"direction": "in"})
    assert denied.status_code == 403
    # Reading payments stays open to staff, as before.
    assert (await async_client.get("/api/v1/payments/summary")).status_code == 200


async def test_open_documents_list_only_balances_owing(owner_client: AsyncClient) -> None:
    partly = await _invoice(owner_client, "Open Partly")
    settled = await _invoice(owner_client, "Open Settled")
    assert (await _pay_in(owner_client, partly["id"], "150.00")).status_code == 201
    assert (await _pay_in(owner_client, settled["id"], "1150.00")).status_code == 201
    bill = await _usd_bill(owner_client, "Open Supplier")

    invoices = await owner_client.get("/api/v1/payments/open-documents", params={"direction": "in"})
    assert invoices.status_code == 200
    by_id = {item["document_id"]: item for item in invoices.json()}
    assert by_id[partly["id"]]["outstanding_foreign"] == "1000.00"
    assert by_id[partly["id"]]["contact_name"] == "Open Partly"
    assert settled["id"] not in by_id
    assert all(item["kind"] == "invoice" for item in invoices.json())

    bills = await owner_client.get("/api/v1/payments/open-documents", params={"direction": "out"})
    match = next(item for item in bills.json() if item["document_id"] == bill["id"])
    assert match["currency"] == "USD"
    assert match["outstanding_foreign"] == "100.00"


async def test_payment_create_and_void_lock_the_document_row(
    owner_client: AsyncClient, async_engine: AsyncEngine
) -> None:
    invoice = await _invoice(owner_client, "Lock Customer")
    bill = await _usd_bill(owner_client, "Lock Supplier")
    statements: list[str] = []

    def capture(_conn, _cursor, statement, *_args) -> None:
        if "FOR UPDATE" in statement:
            statements.append(statement)

    event.listen(async_engine.sync_engine, "before_cursor_execute", capture)
    try:
        paid_in = await _pay_in(owner_client, invoice["id"], "100.00", tender="eft")
        assert paid_in.status_code == 201, paid_in.text
        paid_out = await owner_client.post(
            "/api/v1/payments",
            json={
                "direction": "out",
                "bill_id": bill["id"],
                "amount": "10.00",
                "currency": "USD",
                "fx_to_zar": "18.00",
                "paid_on": TODAY,
                "tender": "eft",
            },
        )
        assert paid_out.status_code == 201, paid_out.text
        locked_on_create = list(statements)
        statements.clear()
        assert (await _void(owner_client, paid_in.json()["id"])).status_code == 200
        assert (await _void(owner_client, paid_out.json()["id"])).status_code == 200
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", capture)

    for locked in (locked_on_create, statements):
        assert any("FROM tax_invoices" in statement for statement in locked)
        assert any("FROM bills" in statement for statement in locked)
