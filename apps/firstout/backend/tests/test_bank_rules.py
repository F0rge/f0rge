"""B5 bank rules: suggest on unmatched CSV lines, apply journal, recode (#566)."""

from __future__ import annotations

from httpx import AsyncClient


TELEPHONE_CSV = """Date,Description,Reference,Amount
2026-09-10,TELKOM TELEPHONE 082,TEL001,-450.00
"""


async def _accounts_by_code(client: AsyncClient) -> dict[str, dict]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account for account in resp.json()}


async def _create_telephone_rule(client: AsyncClient, accounts: dict[str, dict]) -> dict:
    resp = await client.post(
        "/api/v1/bank-rules",
        json={
            "bank_account_id": accounts["1100"]["id"],
            "pattern": "TELEPHONE",
            "target_account_id": accounts["5000"]["id"],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_apply_telephone_rule_posts_journal_and_drops_unmatched(
    owner_client: AsyncClient,
) -> None:
    accounts = await _accounts_by_code(owner_client)
    rule = await _create_telephone_rule(owner_client, accounts)

    upload = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("tel.csv", TELEPHONE_CSV.encode(), "text/csv")},
    )
    assert upload.status_code == 201
    body = upload.json()
    line = body["lines"][0]
    assert line["suggested_rule_id"] == rule["id"]
    assert line["suggested_rule_pattern"] == "TELEPHONE"
    assert line["suggested_account_code"] == "5000"
    assert line["matched_journal_id"] is None

    counts_before = await owner_client.get("/api/v1/bank-imports/unmatched-counts")
    assert counts_before.status_code == 200
    before = {row["account_code"]: row["unmatched_count"] for row in counts_before.json()}
    assert before["1100"] == 1

    applied = await owner_client.post(
        f"/api/v1/bank-imports/{body['id']}/lines/{line['id']}/apply-rule",
        json={"rule_id": rule["id"]},
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["matched_journal_id"] is not None
    assert applied_body["suggested_rule_id"] is None

    counts_after = await owner_client.get("/api/v1/bank-imports/unmatched-counts")
    after = {row["account_code"]: row["unmatched_count"] for row in counts_after.json()}
    assert after["1100"] == 0

    journal = await owner_client.get(f"/api/v1/journals/{applied_body['matched_journal_id']}")
    assert journal.status_code == 200
    posted = journal.json()
    assert posted["status"] == "posted"
    assert posted["document_type"] == "manual"
    assert posted["source"] == "bank-rule"
    assert posted["journal_number"].startswith("JE-")
    by_code = {row["account_code"]: row for row in posted["lines"]}
    assert by_code["5000"]["debit_zar"] == "450.00"
    assert by_code["5000"]["credit_zar"] == "0.00"
    assert by_code["1100"]["debit_zar"] == "0.00"
    assert by_code["1100"]["credit_zar"] == "450.00"


async def test_recode_journal_matched_line_to_other_expense(owner_client: AsyncClient) -> None:
    accounts = await _accounts_by_code(owner_client)
    rule = await _create_telephone_rule(owner_client, accounts)
    upload = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("tel.csv", TELEPHONE_CSV.encode(), "text/csv")},
    )
    assert upload.status_code == 201
    body = upload.json()
    line_id = body["lines"][0]["id"]
    applied = await owner_client.post(
        f"/api/v1/bank-imports/{body['id']}/lines/{line_id}/apply-rule",
        json={"rule_id": rule["id"]},
    )
    assert applied.status_code == 200
    journal_id = applied.json()["matched_journal_id"]

    recode = await owner_client.post(
        f"/api/v1/bank-imports/{body['id']}/lines/{line_id}/recode",
        json={"account_id": accounts["5010"]["id"]},
    )
    assert recode.status_code == 200

    journal = await owner_client.get(f"/api/v1/journals/{journal_id}")
    assert journal.status_code == 200
    by_code = {row["account_code"]: row for row in journal.json()["lines"]}
    assert "5010" in by_code
    assert by_code["5010"]["debit_zar"] == "450.00"
    assert by_code["1100"]["credit_zar"] == "450.00"
    assert "5000" not in by_code


async def test_inactive_rule_does_not_suggest(owner_client: AsyncClient) -> None:
    accounts = await _accounts_by_code(owner_client)
    rule = await _create_telephone_rule(owner_client, accounts)
    patched = await owner_client.patch(
        f"/api/v1/bank-rules/{rule['id']}",
        json={"is_active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    upload = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("tel.csv", TELEPHONE_CSV.encode(), "text/csv")},
    )
    assert upload.status_code == 201
    line = upload.json()["lines"][0]
    assert line["suggested_rule_id"] is None
    assert line["suggested_rule_pattern"] is None
    assert line["suggested_account_code"] is None
