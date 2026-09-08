"""B1 per-category CoA posting (#562)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient

from tests.test_ledger_invoices import _create_customer
from tests.test_purchase_orders import _create_till, _relogin_owner
from tests.test_stock_adjustments import (
    _account_balances,
    _create_sku_with_opening,
    _kramerville_id,
)
from tests.test_till import _set_retail_price, _transfer_to_bedfordview
from tests.test_transfers import _receive_qty_at_location


async def test_seed_includes_category_sales_and_cogs(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    codes = {account["code"] for account in resp.json()}
    assert "4010" in codes
    assert "5010" in codes


async def test_till_sale_of_seating_sku_hits_4010_on_pnl(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="CAT-TILL-SEAT",
    )
    sku_id = data["sku"]["id"]
    patch = await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"category": "Seating"})
    assert patch.status_code == 200
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201
    ex_vat = sale.json()["subtotal_ex_vat"]

    await _relogin_owner(owner_client)
    today = date.today()
    pnl = await owner_client.get(
        "/api/v1/reports/profit-loss",
        params={
            "from": min(date(2026, 9, 1), today).isoformat(),
            "to": max(date(2026, 9, 30), today).isoformat(),
        },
    )
    assert pnl.status_code == 200
    body = pnl.json()
    income = {line["code"]: line["amount_zar"] for line in body["income"]}
    assert "4010" in income
    assert Decimal(income["4010"]) == Decimal(ex_vat)
    assert income.get("4000", "0") in ("0", "0.00") or "4000" not in income


async def test_books_invoice_without_sku_still_credits_4000(owner_client: AsyncClient) -> None:
    customer_id = await _create_customer(owner_client)
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Dining table", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert resp.status_code == 201
    balances = await _account_balances(owner_client)
    assert balances["4000"] == "-1000.00"


async def test_damage_on_seating_sku_hits_stock_adj_5110(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    sku = await _create_sku_with_opening(owner_client, "SEAT-DMG", location_id, qty=5)
    patched = await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"category": "Seating"})
    assert patched.status_code == 200

    created = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": location_id, "reason": "damage"},
    )
    assert created.status_code == 201
    adjustment_id = created.json()["id"]
    line = await owner_client.post(
        f"/api/v1/adjustments/{adjustment_id}/lines",
        json={"sku_id": sku["id"], "qty_delta": -2},
    )
    assert line.status_code == 201
    completed = await owner_client.post(f"/api/v1/adjustments/{adjustment_id}/complete")
    assert completed.status_code == 200

    balances = await _account_balances(owner_client)
    assert balances["5110"] == "200.00"
    assert balances["1300"] == "-200.00"

    journals = await owner_client.get("/api/v1/journals")
    assert journals.status_code == 200
    adj_journal = next(
        row
        for row in journals.json()
        if row["document_type"] == "stock_adjustment" and row["document_id"] == adjustment_id
    )
    assert Decimal(adj_journal["debit_total_zar"]) == Decimal(adj_journal["credit_total_zar"])
    assert Decimal(adj_journal["debit_total_zar"]) == Decimal("200.00")


async def test_put_category_map_unknown_code_rejected(owner_client: AsyncClient) -> None:
    resp = await owner_client.put(
        "/api/v1/category-maps",
        json={
            "category": "Seating",
            "sales_code": "ZZZZ",
            "cogs_code": "5010",
            "stock_adj_code": "5110",
            "count_var_code": "5210",
        },
    )
    assert resp.status_code in (400, 404)


async def test_create_invoice_still_returns_201(owner_client: AsyncClient) -> None:
    customer_id = await _create_customer(owner_client)
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Chair", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["invoice_number"].startswith("INV-")
