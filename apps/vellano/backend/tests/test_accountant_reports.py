"""B3 accountant pack reports (#564): trial balance, journal report, cash summary."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.test_journals import _account_ids, _manual_body


async def _post_manual(owner_client: AsyncClient, *, status: str = "posted") -> dict:
    accounts = await _account_ids(owner_client)
    resp = await owner_client.post("/api/v1/journals", json=_manual_body(accounts, status=status))
    assert resp.status_code == 201
    return resp.json()


def _tb_by_code(body: dict) -> dict[str, dict]:
    return {line["code"]: line for line in body["lines"]}


def _cash_by_code(body: dict) -> dict[str, dict]:
    return {row["code"]: row for row in body["accounts"]}


async def test_trial_balance_equals_after_posted_manual(owner_client: AsyncClient) -> None:
    await _post_manual(owner_client)
    resp = await owner_client.get(
        "/api/v1/reports/trial-balance",
        params={"as_of": "2026-09-01"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total_debit_zar"]) == Decimal(body["total_credit_zar"])
    by_code = _tb_by_code(body)
    assert by_code["5000"]["debit_zar"] == "100.00"
    assert by_code["1100"]["credit_zar"] == "100.00"


async def test_journal_report_lists_manual_and_filters_source(
    owner_client: AsyncClient,
) -> None:
    created = await _post_manual(owner_client)
    listed = await owner_client.get(
        "/api/v1/reports/journals",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert listed.status_code == 200
    entries = listed.json()["entries"]
    manuals = [row for row in entries if row["journal_number"] == created["journal_number"]]
    assert len(manuals) == 1
    assert manuals[0]["source"] == "manual"
    assert manuals[0]["status"] == "posted"
    assert len(manuals[0]["lines"]) == 2

    voided = await owner_client.get(
        "/api/v1/reports/journals",
        params={"from": "2026-09-01", "to": "2026-09-30", "source": "void"},
    )
    assert voided.status_code == 200
    assert voided.json()["entries"] == []


async def test_cash_summary_credits_bank_as_out(owner_client: AsyncClient) -> None:
    await _post_manual(owner_client)
    resp = await owner_client.get(
        "/api/v1/reports/cash-summary",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    bank = _cash_by_code(resp.json())["1100"]
    assert bank["cash_in_zar"] in ("0", "0.00")
    assert bank["cash_out_zar"] == "100.00"


async def test_accountant_csv_endpoints(owner_client: AsyncClient) -> None:
    created = await _post_manual(owner_client)
    journal_number = created["journal_number"].encode()

    tb = await owner_client.get(
        "/api/v1/reports/trial-balance/csv",
        params={"as_of": "2026-09-01"},
    )
    assert tb.status_code == 200
    assert "text/csv" in tb.headers["content-type"]
    assert b"5000" in tb.content or b"1100" in tb.content

    journals = await owner_client.get(
        "/api/v1/reports/journals/csv",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert journals.status_code == 200
    assert "text/csv" in journals.headers["content-type"]
    assert journal_number in journals.content

    cash = await owner_client.get(
        "/api/v1/reports/cash-summary/csv",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert cash.status_code == 200
    assert "text/csv" in cash.headers["content-type"]
    assert b"1100" in cash.content


async def test_draft_excluded_from_trial_balance_and_cash(owner_client: AsyncClient) -> None:
    await _post_manual(owner_client, status="draft")
    tb = await owner_client.get(
        "/api/v1/reports/trial-balance",
        params={"as_of": "2026-09-01"},
    )
    assert tb.status_code == 200
    codes = set(_tb_by_code(tb.json()))
    assert "5000" not in codes
    assert "1100" not in codes
    assert Decimal(tb.json()["total_debit_zar"]) == Decimal(tb.json()["total_credit_zar"])

    cash = await owner_client.get(
        "/api/v1/reports/cash-summary",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert cash.status_code == 200
    bank = _cash_by_code(cash.json())["1100"]
    assert Decimal(bank["cash_in_zar"]) == 0
    assert Decimal(bank["cash_out_zar"]) == 0
