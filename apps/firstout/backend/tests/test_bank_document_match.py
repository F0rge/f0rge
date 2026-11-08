"""Suggest and match bank lines to open invoices and bills."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.journal import JournalDocumentType, JournalEntry, JournalLine
from app.services.bank_match_rank import OpenDocument, rank_documents, unique_auto_match


def test_exact_reference_ranks_above_a_partial_name_match() -> None:
    exact_id = uuid4()
    partial_id = uuid4()
    documents = [
        OpenDocument(
            kind="invoice",
            document_id=partial_id,
            number="INV-0002",
            contact_name="Partial Customer",
            outstanding_zar=Decimal("2000.00"),
            issue_date=date(2026, 9, 1),
            currency="ZAR",
            outstanding_foreign=Decimal("2000.00"),
            fx_to_zar=Decimal("1"),
        ),
        OpenDocument(
            kind="invoice",
            document_id=exact_id,
            number="INV-0001",
            contact_name="Exact Customer",
            outstanding_zar=Decimal("1150.00"),
            issue_date=date(2026, 9, 1),
            currency="ZAR",
            outstanding_foreign=Decimal("1150.00"),
            fx_to_zar=Decimal("1"),
        ),
    ]
    ranked = rank_documents(
        amount_zar=Decimal("1150.00"),
        transaction_date=date(2026, 9, 2),
        description="EFT from Partial Customer INV-0001",
        reference="REF",
        documents=documents,
    )
    assert [item.document.number for item in ranked] == ["INV-0001", "INV-0002"]
    assert ranked[0].exact_amount is True
    assert ranked[0].confidence > ranked[1].confidence
    assert ranked[0].auto_match is True
    assert ranked[1].auto_match is False
    assert "exact outstanding balance" in ranked[0].reason
    assert "part of the outstanding balance" in ranked[1].reason
    chosen = unique_auto_match(ranked)
    assert chosen is not None
    assert chosen.document.document_id == exact_id


def test_two_exact_references_are_not_an_automatic_match() -> None:
    documents = [
        OpenDocument(
            kind="invoice",
            document_id=uuid4(),
            number="INV-0001",
            contact_name="A",
            outstanding_zar=Decimal("100.00"),
            issue_date=date(2026, 9, 1),
            currency="ZAR",
            outstanding_foreign=Decimal("100.00"),
            fx_to_zar=Decimal("1"),
        ),
        OpenDocument(
            kind="invoice",
            document_id=uuid4(),
            number="INV-0001-OLD",
            contact_name="B",
            outstanding_zar=Decimal("100.00"),
            issue_date=date(2026, 9, 1),
            currency="ZAR",
            outstanding_foreign=Decimal("100.00"),
            fx_to_zar=Decimal("1"),
        ),
    ]
    ranked = rank_documents(
        amount_zar=Decimal("100.00"),
        transaction_date=date(2026, 9, 2),
        description="Pay INV-0001 and INV-0001-OLD",
        reference=None,
        documents=documents,
    )
    assert unique_auto_match(ranked) is None


async def _invoice(owner_client: AsyncClient, name: str, unit_ex_vat: str) -> dict:
    customer = await owner_client.post("/api/v1/customers", json={"name": name})
    assert customer.status_code == 201
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": unit_ex_vat}],
        },
    )
    assert invoice.status_code == 201
    return invoice.json()


async def _zar_bill(owner_client: AsyncClient, name: str, unit_amount: str) -> dict:
    supplier = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": name, "default_currency": "ZAR"},
    )
    assert supplier.status_code == 201
    bill = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier.json()["id"],
            "supplier_ref": "LOCAL",
            "issue_date": "2026-09-01",
            "currency": "ZAR",
            "lines": [{"description": "Timber", "qty": 1, "unit_amount": unit_amount}],
        },
    )
    assert bill.status_code == 201
    return bill.json()


async def _upload(owner_client: AsyncClient, csv_text: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("bank.csv", csv_text.encode(), "text/csv")},
    )
    assert resp.status_code == 201
    return resp.json()


def _line(bank_import: dict, amount: str) -> dict:
    return next(line for line in bank_import["lines"] if line["amount_zar"] == amount)


async def _balances(owner_client: AsyncClient) -> dict[str, str]:
    resp = await owner_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["balance_zar"] for account in resp.json()}


async def _payment_lines(async_db: AsyncSession, payment_id: str) -> list[tuple[str, str, str]]:
    rows = (
        await async_db.execute(
            select(Account.code, JournalLine.debit_zar, JournalLine.credit_zar)
            .join(JournalLine, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                JournalEntry.document_type == JournalDocumentType.PAYMENT,
                JournalEntry.document_id == UUID(payment_id),
            )
        )
    ).all()
    return sorted((code, f"{debit:.2f}", f"{credit:.2f}") for code, debit, credit in rows)


async def test_suggestions_rank_exact_invoice_and_bill(
    owner_client: AsyncClient,
) -> None:
    exact = await _invoice(owner_client, "Exact Rank Customer", "1000.00")
    await _invoice(owner_client, "Partial Rank Customer", "2000.00")
    bill = await _zar_bill(owner_client, "Rank Supplier", "100.00")
    uploaded = await _upload(
        owner_client,
        "\n".join(
            [
                "Date,Description,Reference,Amount",
                f"2026-09-02,EFT {exact['invoice_number']},REF1,{exact['total_inc_vat']}",
                f"2026-09-03,Pay {bill['bill_number']},REF2,-{bill['amount_zar']}",
                "2026-09-04,Partial Rank Customer deposit,REF3,400.00",
            ]
        ),
    )
    money_in = _line(uploaded, exact["total_inc_vat"])
    assert money_in["document_suggestions"][0]["document_number"] == exact["invoice_number"]
    assert money_in["document_suggestions"][0]["auto_match"] is True
    assert (
        money_in["document_suggestions"][0]["confidence"]
        > money_in["document_suggestions"][1]["confidence"]
    )
    assert "exact outstanding balance" in money_in["document_suggestions"][0]["reason"]

    money_out = _line(uploaded, f"-{bill['amount_zar']}")
    assert money_out["document_suggestions"][0]["kind"] == "bill"
    assert money_out["document_suggestions"][0]["document_number"] == bill["bill_number"]
    assert money_out["document_suggestions"][0]["auto_match"] is True

    partial = _line(uploaded, "400.00")
    assert partial["document_suggestions"][0]["auto_match"] is False
    assert "part of the outstanding balance" in partial["document_suggestions"][0]["reason"]


async def test_match_document_posts_a_partial_payment(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    invoice = await _invoice(owner_client, "Partial Match Customer", "1000.00")
    uploaded = await _upload(
        owner_client,
        "Date,Description,Reference,Amount\n2026-09-02,Part payment,REF,400.00\n",
    )
    line = uploaded["lines"][0]
    matched = await owner_client.post(
        f"/api/v1/bank-imports/{uploaded['id']}/lines/{line['id']}/match-document",
        json={"invoice_id": invoice["id"]},
    )
    assert matched.status_code == 200
    body = matched.json()
    assert body["matched_payment_id"] is not None
    assert body["allocations"][0]["document_number"] == invoice["invoice_number"]
    assert body["allocations"][0]["amount_zar"] == "400.00"

    detail = await owner_client.get(f"/api/v1/invoices/{invoice['id']}")
    assert detail.json()["payment_status"] == "partially_paid"
    assert detail.json()["balance"] == "750.00"
    balances = await _balances(owner_client)
    assert balances["1100"] == "400.00"
    assert balances["1200"] == "750.00"
    assert await _payment_lines(async_db, body["matched_payment_id"]) == [
        ("1100", "400.00", "0.00"),
        ("1200", "0.00", "400.00"),
    ]


async def test_split_one_bank_line_across_two_invoices(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    first = await _invoice(owner_client, "Split One", "400.00")
    second = await _invoice(owner_client, "Split Two", "600.00")
    total = Decimal(first["total_inc_vat"]) + Decimal(second["total_inc_vat"])
    uploaded = await _upload(
        owner_client,
        f"Date,Description,Reference,Amount\n2026-09-02,Combined receipt,REF,{total:.2f}\n",
    )
    line = uploaded["lines"][0]
    matched = await owner_client.post(
        f"/api/v1/bank-imports/{uploaded['id']}/lines/{line['id']}/split",
        json={
            "allocations": [
                {"invoice_id": first["id"], "amount": first["total_inc_vat"]},
                {"invoice_id": second["id"], "amount": second["total_inc_vat"]},
            ]
        },
    )
    assert matched.status_code == 200
    body = matched.json()
    assert body["matched_payment_id"] is not None
    assert sorted(item["amount_zar"] for item in body["allocations"]) == sorted(
        [first["total_inc_vat"], second["total_inc_vat"]]
    )
    for invoice in (first, second):
        detail = await owner_client.get(f"/api/v1/invoices/{invoice['id']}")
        assert detail.json()["payment_status"] == "paid"
        assert detail.json()["balance"] == "0.00"
    balances = await _balances(owner_client)
    assert balances["1100"] == f"{total:.2f}"
    assert balances["1200"] == "0.00"
    for allocation in body["allocations"]:
        lines = await _payment_lines(async_db, allocation["payment_id"])
        debit = next(row for row in lines if row[0] == "1100")
        credit = next(row for row in lines if row[0] == "1200")
        assert debit[1] == allocation["amount_zar"]
        assert credit[2] == allocation["amount_zar"]


async def test_auto_match_preview_does_not_post_until_confirm(
    owner_client: AsyncClient,
) -> None:
    invoice = await _invoice(owner_client, "Auto Match Customer", "1000.00")
    await _invoice(owner_client, "Not Auto Customer", "1000.00")
    uploaded = await _upload(
        owner_client,
        "\n".join(
            [
                "Date,Description,Reference,Amount",
                f"2026-09-02,Thanks {invoice['invoice_number']},REF,{invoice['total_inc_vat']}",
                "2026-09-04,Loose deposit,REF2,400.00",
            ]
        ),
    )
    before = await owner_client.get("/api/v1/payments")
    assert before.status_code == 200
    preview = await owner_client.post("/api/v1/bank-imports/auto-match/preview")
    assert preview.status_code == 200
    matches = preview.json()["matches"]
    assert len(matches) == 1
    assert matches[0]["document_number"] == invoice["invoice_number"]
    assert matches[0]["line_id"] == _line(uploaded, invoice["total_inc_vat"])["id"]
    after_preview = await owner_client.get("/api/v1/payments")
    assert after_preview.json()["items"] == before.json()["items"]

    confirmed = await owner_client.post(
        "/api/v1/bank-imports/auto-match/confirm",
        json={"line_ids": [matches[0]["line_id"]]},
    )
    assert confirmed.status_code == 200
    assert len(confirmed.json()["applied"]) == 1
    assert confirmed.json()["skipped"] == []
    detail = await owner_client.get(f"/api/v1/invoices/{invoice['id']}")
    assert detail.json()["payment_status"] == "paid"
    balances = await _balances(owner_client)
    assert balances["1100"] == invoice["total_inc_vat"]
    assert balances["1200"] == invoice["total_inc_vat"]

    again = await owner_client.post(
        "/api/v1/bank-imports/auto-match/confirm",
        json={"line_ids": [matches[0]["line_id"]]},
    )
    assert again.status_code == 200
    assert again.json()["applied"] == []
    assert again.json()["skipped"]
