"""S7 financial reports and VAT201 draft tests."""

from __future__ import annotations

import subprocess
from decimal import Decimal

from httpx import AsyncClient


async def _create_invoice(owner_client: AsyncClient, ex_vat: str = "1000.00") -> dict:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Report Customer"},
    )
    assert customer_resp.status_code == 201
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": ex_vat}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_unauthenticated_profit_loss_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/api/v1/reports/profit-loss",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 401


async def test_profit_loss_includes_sales(owner_client: AsyncClient) -> None:
    await _create_invoice(owner_client)
    resp = await owner_client.get(
        "/api/v1/reports/profit-loss",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_income_zar"] == "1000.00"
    sales = next(line for line in body["income"] if line["code"] == "4000")
    assert sales["amount_zar"] == "1000.00"


async def test_balance_sheet_lists_assets(owner_client: AsyncClient) -> None:
    await _create_invoice(owner_client)
    resp = await owner_client.get(
        "/api/v1/reports/balance-sheet",
        params={"as_of": "2026-09-30"},
    )
    assert resp.status_code == 200
    body = resp.json()
    codes = {line["code"] for line in body["assets"]}
    assert "1200" in codes


async def test_aged_ar_shows_unpaid_invoice(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(owner_client)
    resp = await owner_client.get(
        "/api/v1/reports/aged-ar",
        params={"as_of": "2026-09-15"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_zar"] == "1150.00"
    assert any(line["document_number"] == invoice["invoice_number"] for line in body["lines"])


async def test_vat201_draft_totals_15_percent(owner_client: AsyncClient) -> None:
    await _create_invoice(owner_client, ex_vat="1000.00")
    resp = await owner_client.get(
        "/api/v1/reports/vat201",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["standard_rated_supplies_ex_vat"] == "1000.00"
    assert body["output_tax"] == "150.00"
    assert Decimal(body["output_tax"]) == Decimal(body["standard_rated_supplies_ex_vat"]) * Decimal(
        "0.15"
    )
    assert body["net_vat_payable"] == "150.00"
    assert "eFiling" in body["disclaimer"]
    assert "SARS" in body["disclaimer"]


async def test_vat201_csv_download(owner_client: AsyncClient) -> None:
    await _create_invoice(owner_client)
    resp = await owner_client.get(
        "/api/v1/reports/vat201/csv",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert b"VAT201 Draft" in resp.content


async def test_vat201_pdf_download(owner_client: AsyncClient) -> None:
    await _create_invoice(owner_client)
    resp = await owner_client.get(
        "/api/v1/reports/vat201/pdf",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_no_sars_http_client_in_vellano_backend() -> None:
    result = subprocess.run(
        ["rg", "-l", "sars\\.gov\\.za", "apps/vellano/backend/app"],
        capture_output=True,
        text=True,
        cwd="/workspace",
        check=False,
    )
    assert result.stdout.strip() == "", f"Found sars.gov.za references: {result.stdout}"
