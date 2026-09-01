"""B2 bank accounts as CSV recon targets (#563)."""

from __future__ import annotations

from httpx import AsyncClient


SAMPLE_CSV = """Date,Description,Reference,Amount
2026-09-02,Customer payment INV-0001,REF001,1150.00
2026-09-03,Supplier payment BILL-0001,REF002,-1800.00
2026-09-04,Unmatched deposit,REF003,500.00
"""

CC_CSV = """Date,Description,Reference,Amount
2026-09-05,Card purchase,CC001,-250.00
"""


async def _accounts_by_code(client: AsyncClient) -> dict[str, dict]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account for account in resp.json()}


async def test_bank_accounts_seeded_is_bank(owner_client: AsyncClient) -> None:
    accounts = await _accounts_by_code(owner_client)
    assert accounts["1100"]["is_bank"] is True
    assert accounts["1100"]["name"] == "Bank"
    assert accounts["1110"]["name"] == "Credit card"
    assert accounts["1110"]["is_bank"] is True
    assert accounts["1120"]["is_bank"] is True
    assert accounts["1130"]["is_bank"] is True
    assert accounts["1140"]["is_bank"] is True


async def test_upload_to_credit_card_unmatched_is_account_scoped(
    owner_client: AsyncClient,
) -> None:
    accounts = await _accounts_by_code(owner_client)
    files = {"file": ("cc.csv", CC_CSV.encode(), "text/csv")}
    resp = await owner_client.post(
        "/api/v1/bank-imports",
        files=files,
        data={"account_id": accounts["1110"]["id"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_code"] == "1110"
    assert body["account_name"] == "Credit card"
    assert len(body["lines"]) == 1

    cc_lines = await owner_client.get(
        "/api/v1/bank-imports/unmatched-lines",
        params={"account_id": accounts["1110"]["id"]},
    )
    assert cc_lines.status_code == 200
    assert len(cc_lines.json()) == 1
    assert cc_lines.json()[0]["id"] == body["lines"][0]["id"]

    bank_lines = await owner_client.get(
        "/api/v1/bank-imports/unmatched-lines",
        params={"account_id": accounts["1100"]["id"]},
    )
    assert bank_lines.status_code == 200
    assert bank_lines.json() == []


async def test_two_accounts_each_have_an_import(owner_client: AsyncClient) -> None:
    accounts = await _accounts_by_code(owner_client)
    bank_resp = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")},
    )
    assert bank_resp.status_code == 201
    assert bank_resp.json()["account_code"] == "1100"

    cc_resp = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("cc.csv", CC_CSV.encode(), "text/csv")},
        data={"account_id": accounts["1110"]["id"]},
    )
    assert cc_resp.status_code == 201
    assert cc_resp.json()["account_code"] == "1110"

    listed = await owner_client.get("/api/v1/bank-imports")
    assert listed.status_code == 200
    codes = {row["account_code"] for row in listed.json()}
    assert "1100" in codes
    assert "1110" in codes


async def test_match_posted_manual_journal_marks_line(
    owner_client: AsyncClient,
) -> None:
    accounts = await _accounts_by_code(owner_client)
    upload = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("cc.csv", CC_CSV.encode(), "text/csv")},
        data={"account_id": accounts["1110"]["id"]},
    )
    assert upload.status_code == 201
    import_body = upload.json()
    line_id = import_body["lines"][0]["id"]

    counts_before = await owner_client.get("/api/v1/bank-imports/unmatched-counts")
    assert counts_before.status_code == 200
    before = {row["account_code"]: row["unmatched_count"] for row in counts_before.json()}
    assert before["1110"] == 1
    assert before["1100"] == 0

    journal = await owner_client.post(
        "/api/v1/journals",
        json={
            "entry_date": "2026-09-05",
            "memo": "Card purchase",
            "status": "posted",
            "lines": [
                {
                    "account_id": accounts["5000"]["id"],
                    "debit_zar": "250.00",
                    "credit_zar": "0.00",
                },
                {
                    "account_id": accounts["1110"]["id"],
                    "debit_zar": "0.00",
                    "credit_zar": "250.00",
                },
            ],
        },
    )
    assert journal.status_code == 201
    journal_id = journal.json()["id"]

    match = await owner_client.post(
        f"/api/v1/bank-imports/{import_body['id']}/lines/{line_id}/match",
        json={"journal_id": journal_id},
    )
    assert match.status_code == 200
    assert match.json()["matched_journal_id"] == journal_id
    assert match.json()["matched_payment_id"] is None

    counts_after = await owner_client.get("/api/v1/bank-imports/unmatched-counts")
    after = {row["account_code"]: row["unmatched_count"] for row in counts_after.json()}
    assert after["1110"] == 0

    leftover = await owner_client.get(
        "/api/v1/bank-imports/unmatched-lines",
        params={"account_id": accounts["1110"]["id"]},
    )
    assert leftover.json() == []

    posted = await owner_client.get(f"/api/v1/journals/{journal_id}")
    assert posted.status_code == 200
    assert posted.json()["status"] == "posted"


async def test_payment_match_still_works_on_default_bank(
    owner_client: AsyncClient,
) -> None:
    customer = await owner_client.post("/api/v1/contacts", json={"name": "Bank Recon"})
    assert customer.status_code == 201
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert invoice.status_code == 201
    payment = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice.json()["id"],
            "amount": "1150.00",
            "currency": "ZAR",
            "paid_on": "2026-09-02",
        },
    )
    assert payment.status_code == 201

    upload = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")},
    )
    assert upload.status_code == 201
    import_body = upload.json()
    assert import_body["account_code"] == "1100"
    line_id = import_body["lines"][0]["id"]

    match = await owner_client.post(
        f"/api/v1/bank-imports/{import_body['id']}/lines/{line_id}/match",
        json={"payment_id": payment.json()["id"]},
    )
    assert match.status_code == 200
    assert match.json()["matched_payment_id"] == payment.json()["id"]


async def test_upload_without_account_id_defaults_to_1100(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("bank.csv", SAMPLE_CSV.encode(), "text/csv")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_code"] == "1100"
    assert body["account_name"] == "Bank"
    assert body["line_count"] == 3
