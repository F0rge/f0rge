"""Firstout ADR 0003: a sale document keeps the VAT rate it was computed at.

Each test makes a document at the team's 15%, changes the setting to 16%, and shows that
reprints, credit notes, conversions and layby completion stay at the stored 15%, while a
new document takes 16%.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.test_laybys import (
    _create_customer,
    _create_till_user,
    _layby_payload,
    _stocked_sku_at_bedford,
)
from tests.test_ledger_credit_notes import _create_invoice, _pdf_text
from tests.test_purchase_orders import _location_id_by_name
from tests.test_quotes import _named_customer
from tests.test_till import _set_retail_price
from tests.test_transfers import _receive_qty_at_location


async def _set_vat_rate(owner_client: AsyncClient, rate: str) -> None:
    resp = await owner_client.patch("/api/v1/settings", json={"vat_rate": rate})
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["vat_rate"]) == Decimal(rate)


async def test_reprint_and_credit_note_keep_the_invoice_rate(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(owner_client)  # R2000.00 ex VAT
    assert Decimal(invoice["vat_rate"]) == Decimal("0.15")
    assert invoice["vat_amount"] == "300.00"

    await _set_vat_rate(owner_client, "0.16")

    reprint = await owner_client.get(f"/api/v1/invoices/{invoice['id']}/pdf")
    assert reprint.status_code == 200
    text = _pdf_text(reprint.content)
    assert "VAT (15%)" in text and "16%" not in text

    credit = await owner_client.post(
        "/api/v1/credit-notes", json={"invoice_id": invoice["id"], "reason": "Returned"}
    )
    assert credit.status_code == 201, credit.text
    assert Decimal(credit.json()["vat_rate"]) == Decimal("0.15")
    assert credit.json()["vat_amount"] == "300.00"
    credit_pdf = await owner_client.get(f"/api/v1/credit-notes/{credit.json()['id']}/pdf")
    assert "VAT (15%)" in _pdf_text(credit_pdf.content)

    # A new document takes the new rate.
    fresh = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": invoice["customer_id"],
            "issue_date": "2026-09-02",
            "lines": [{"description": "Sofa", "qty": 1, "unit_ex_vat": "2000.00"}],
        },
    )
    assert fresh.status_code == 201, fresh.text
    fresh = fresh.json()
    assert Decimal(fresh["vat_rate"]) == Decimal("0.16")
    assert (fresh["vat_amount"], fresh["total_inc_vat"]) == ("320.00", "2320.00")
    fresh_pdf = await owner_client.get(f"/api/v1/invoices/{fresh['id']}/pdf")
    assert "VAT (16%)" in _pdf_text(fresh_pdf.content)


async def test_quote_to_order_to_invoice_keeps_the_quote_rate(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    data = await _receive_qty_at_location(
        async_client, owner_client, qty=1, location_name="Kramerville", our_ref="VAT-SNAP-QT"
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    customer_id = await _named_customer(owner_client, "VAT snapshot quote")
    quote = await owner_client.post(
        "/api/v1/quotes", json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]}
    )
    assert quote.status_code == 201, quote.text
    assert Decimal(quote.json()["vat_rate"]) == Decimal("0.15")

    await _set_vat_rate(owner_client, "0.16")

    location_id = await _location_id_by_name(owner_client, "Kramerville")
    order = await owner_client.post(
        f"/api/v1/quotes/{quote.json()['id']}/accept",
        json={"location_id": location_id, "hold_stock": False},
    )
    assert order.status_code == 200, order.text
    assert Decimal(order.json()["vat_rate"]) == Decimal("0.15")
    assert order.json()["vat_amount"] == "150.00"

    invoiced = await owner_client.post(f"/api/v1/orders/{order.json()['id']}/invoice")
    assert invoiced.status_code == 200, invoiced.text
    invoice = await owner_client.get(f"/api/v1/invoices/{invoiced.json()['invoice_id']}")
    assert Decimal(invoice.json()["vat_rate"]) == Decimal("0.15")
    assert (invoice.json()["vat_amount"], invoice.json()["total_inc_vat"]) == (
        "150.00",
        "1150.00",
    )


async def test_layby_completion_invoices_at_the_rate_it_was_concluded_at(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "VAT-SNAP-LB")
    customer_id = await _create_customer(owner_client)
    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys", json=_layby_payload(customer_id, bedford_id, sku_id, deposit="1150.00")
    )
    assert created.status_code == 201, created.text
    assert Decimal(created.json()["vat_rate"]) == Decimal("0.15")

    # The owner's session was replaced by the till login; the till cannot edit settings,
    # so the rate changes behind it in the shared database.
    from app.crud.team_settings import TeamSettingsCRUD
    from app.crud.user import TeamCRUD

    db = async_client.test_db
    team = await TeamCRUD(db).get_first()
    settings = await TeamSettingsCRUD(db).get_or_create_for_team(team.id)
    settings.vat_rate = Decimal("0.16")
    await db.flush()

    completed = await till.post(f"/api/v1/laybys/{created.json()['id']}/complete")
    assert completed.status_code == 200, completed.text
    invoice = await till.get(f"/api/v1/invoices/{completed.json()['invoice_id']}")
    assert invoice.status_code == 200, invoice.text
    # SARS 2018 FAQ Q13: the layby's rate, not the one in force at completion.
    assert Decimal(invoice.json()["vat_rate"]) == Decimal("0.15")
    assert (invoice.json()["vat_amount"], invoice.json()["total_inc_vat"]) == (
        "150.00",
        "1150.00",
    )
