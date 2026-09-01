"""B0 manual journals (#561)."""

from __future__ import annotations

from httpx import AsyncClient


async def _account_ids(client: AsyncClient) -> dict[str, str]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["id"] for account in resp.json()}


async def _account_balances(client: AsyncClient) -> dict[str, str]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["balance_zar"] for account in resp.json()}


def _manual_body(
    accounts: dict[str, str],
    *,
    status: str = "posted",
    debit: str = "100.00",
    credit: str = "100.00",
) -> dict:
    return {
        "entry_date": "2026-09-01",
        "memo": "Rent",
        "source": "manual",
        "status": status,
        "lines": [
            {"account_id": accounts["5000"], "debit_zar": debit, "credit_zar": "0.00"},
            {"account_id": accounts["1100"], "debit_zar": "0.00", "credit_zar": credit},
        ],
    }


async def test_unauthenticated_create_journal_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/journals",
        json={
            "entry_date": "2026-09-01",
            "status": "posted",
            "lines": [
                {
                    "account_id": "00000000-0000-0000-0000-000000000001",
                    "debit_zar": "100.00",
                    "credit_zar": "0.00",
                },
                {
                    "account_id": "00000000-0000-0000-0000-000000000002",
                    "debit_zar": "0.00",
                    "credit_zar": "100.00",
                },
            ],
        },
    )
    assert resp.status_code == 401


async def test_till_cannot_create_journal(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    accounts = await _account_ids(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-journals@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-journals@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    resp = await async_client.post("/api/v1/journals", json=_manual_body(accounts))
    assert resp.status_code == 403


async def test_owner_posts_balanced_journal_moves_coa_and_pnl(
    owner_client: AsyncClient,
) -> None:
    accounts = await _account_ids(owner_client)
    resp = await owner_client.post("/api/v1/journals", json=_manual_body(accounts))
    assert resp.status_code == 201
    body = resp.json()
    assert body["journal_number"] == "JE-0001"
    assert body["status"] == "posted"
    assert body["document_type"] == "manual"
    assert body["source"] == "manual"
    assert body["debit_total_zar"] == "100.00"
    assert body["credit_total_zar"] == "100.00"

    balances = await _account_balances(owner_client)
    assert balances["5000"] == "100.00"
    assert balances["1100"] == "-100.00"

    pnl = await owner_client.get(
        "/api/v1/reports/profit-loss",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert pnl.status_code == 200
    expenses = {line["code"]: line["amount_zar"] for line in pnl.json()["expenses"]}
    assert expenses["5000"] == "100.00"


async def test_unbalanced_journal_rejected(owner_client: AsyncClient) -> None:
    accounts = await _account_ids(owner_client)
    resp = await owner_client.post(
        "/api/v1/journals",
        json=_manual_body(accounts, debit="100.00", credit="50.00"),
    )
    assert resp.status_code == 400


async def test_draft_excluded_from_balances_until_posted(owner_client: AsyncClient) -> None:
    accounts = await _account_ids(owner_client)
    before = await _account_balances(owner_client)
    created = await owner_client.post(
        "/api/v1/journals",
        json=_manual_body(accounts, status="draft"),
    )
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert created.json()["journal_number"] == "JE-0001"

    after_draft = await _account_balances(owner_client)
    assert after_draft["5000"] == before["5000"]
    assert after_draft["1100"] == before["1100"]

    posted = await owner_client.post(f"/api/v1/journals/{created.json()['id']}/post")
    assert posted.status_code == 200
    assert posted.json()["status"] == "posted"

    after_post = await _account_balances(owner_client)
    assert after_post["5000"] == "100.00"
    assert after_post["1100"] == "-100.00"


async def test_void_keeps_history_and_nets_to_zero(owner_client: AsyncClient) -> None:
    accounts = await _account_ids(owner_client)
    created = await owner_client.post("/api/v1/journals", json=_manual_body(accounts))
    assert created.status_code == 201
    original_id = created.json()["id"]

    voided = await owner_client.post(f"/api/v1/journals/{original_id}/void")
    assert voided.status_code == 200
    assert voided.json()["status"] == "voided"
    assert voided.json()["id"] == original_id
    reversing_id = voided.json()["voided_by_id"]
    assert reversing_id is not None

    original_get = await owner_client.get(f"/api/v1/journals/{original_id}")
    assert original_get.status_code == 200
    assert original_get.json()["status"] == "voided"

    reversing = await owner_client.get(f"/api/v1/journals/{reversing_id}")
    assert reversing.status_code == 200
    assert reversing.json()["status"] == "posted"
    assert reversing.json()["memo"] == "Void of JE-0001"
    assert reversing.json()["source"] == "void"
    assert reversing.json()["journal_number"] == "JE-0002"

    listed = await owner_client.get("/api/v1/journals")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert original_id in ids
    assert reversing_id in ids

    balances = await _account_balances(owner_client)
    assert balances["5000"] in ("0", "0.00")
    assert balances["1100"] in ("0", "0.00")


async def test_invoice_still_posts_after_journals(owner_client: AsyncClient) -> None:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Journal Smoke Customer"},
    )
    assert customer_resp.status_code == 201
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Table", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert resp.status_code == 201
    balances = await _account_balances(owner_client)
    assert balances["1200"] == "1150.00"
