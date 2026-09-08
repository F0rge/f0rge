"""B7 SimplePay journal CSV import (#568)."""

from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient

BALANCED_CSV = (
    "Date,Narration,Account,Debit,Credit\n"
    "2026-09-01,SimplePay salaries,5000,100.00,\n"
    "2026-09-01,SimplePay salaries,1100,,100.00\n"
)

UNBALANCED_CSV = (
    "Date,Narration,Account,Debit,Credit\n"
    "2026-09-01,SimplePay salaries,5000,100.00,\n"
    "2026-09-01,SimplePay salaries,1100,,50.00\n"
)


def _files(body: str) -> dict:
    return {"file": ("simplepay.csv", BytesIO(body.encode("utf-8")), "text/csv")}


async def _account_balances(client: AsyncClient) -> dict[str, str]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["balance_zar"] for account in resp.json()}


async def test_commit_balanced_csv_posts_journal_and_moves_pnl(
    owner_client: AsyncClient,
) -> None:
    resp = await owner_client.post(
        "/api/v1/journal-imports/commit",
        files=_files(BALANCED_CSV),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["journal_number"].startswith("JE-")
    assert body["source"] == "import:simplepay"
    assert body["status"] == "posted"
    assert body["memo"] == "SimplePay salaries"
    assert body["entry_date"] == "2026-09-01"
    assert body["debit_total_zar"] == "100.00"
    assert body["credit_total_zar"] == "100.00"

    listed = await owner_client.get("/api/v1/journals")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json())

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


async def test_commit_unbalanced_csv_returns_400(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/journal-imports/commit",
        files=_files(UNBALANCED_CSV),
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "balance" in detail or "line" in detail


async def test_second_commit_same_month_returns_409(owner_client: AsyncClient) -> None:
    first = await owner_client.post(
        "/api/v1/journal-imports/commit",
        files=_files(BALANCED_CSV),
    )
    assert first.status_code == 201

    second = await owner_client.post(
        "/api/v1/journal-imports/commit",
        files=_files(BALANCED_CSV),
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "SimplePay import already exists for this month"


async def test_preview_unbalanced_returns_200_with_errors(
    owner_client: AsyncClient,
) -> None:
    resp = await owner_client.post(
        "/api/v1/journal-imports/preview",
        files=_files(UNBALANCED_CSV),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["balanced"] is False
    assert body["errors"]
    assert any("balance" in item["message"].lower() for item in body["errors"])
    assert body["debit_total"] == "100.00"
    assert body["credit_total"] == "50.00"
