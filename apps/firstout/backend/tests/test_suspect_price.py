"""Suspect unit prices warn, and they never block the document or leak cost."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from pypdf import PdfReader

from app.config import settings
from app.services.suspect_price import (
    RESTRICTED_SUSPECT_PRICE_WARNING,
    suspect_unit_price_warning,
)
from tests.test_purchase_orders import _create_till, _location_id_by_name, _relogin_owner
from tests.test_sku_bom import _sku


@pytest.mark.no_db
def test_placeholder_and_below_cost_thresholds() -> None:
    placeholder = suspect_unit_price_warning(Decimal("1.00"), None, reveal_cost=True)
    assert placeholder is not None
    assert "R1.00 or below" in placeholder
    retail_placeholder = suspect_unit_price_warning(Decimal("0.87"), None, reveal_cost=True)
    assert retail_placeholder is not None
    assert "R1.00 or below" in retail_placeholder

    at_cost = suspect_unit_price_warning(Decimal("1.00"), Decimal("1.00"), reveal_cost=True)
    assert at_cost is not None
    assert "below average cost" not in at_cost

    below = suspect_unit_price_warning(Decimal("400.00"), Decimal("1500.00"), reveal_cost=True)
    assert below == "Unit price R400.00 is below average cost R1500.00."

    assert (
        suspect_unit_price_warning(Decimal("800.00"), Decimal("400.00"), reveal_cost=True) is None
    )
    assert suspect_unit_price_warning(Decimal("1.01"), Decimal("0.50"), reveal_cost=True) is None

    hidden = suspect_unit_price_warning(Decimal("400.00"), Decimal("1500.00"), reveal_cost=False)
    assert hidden == RESTRICTED_SUSPECT_PRICE_WARNING
    assert "1500" not in hidden
    assert "400" not in hidden


async def _customer(client: AsyncClient, name: str, classification: str) -> str:
    created = await client.post(
        "/api/v1/customers",
        json={"name": name, "price_classification": classification},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _login(client: AsyncClient, email: str, password: str) -> None:
    client.cookies.clear()
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text


async def test_quote_warns_for_placeholder_below_cost_and_a_normal_price(
    owner_client: AsyncClient,
) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    sku = await _sku(
        owner_client,
        "SUS-MIX",
        opening_location_id=location_id,
        opening_qty=2,
        opening_cost="1500.00",
        retail_ex_vat="0.87",
    )
    priced = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"stockist_ex_vat": "400.00", "wholesale_ex_vat": "2000.00", "retail_ex_vat": "0.87"},
    )
    assert priced.status_code == 200, priced.text
    assert Decimal(priced.json()["average_unit_cost_zar"]) == Decimal("1500.00")
    assert priced.json()["stockist_below_cost"] is True
    assert priced.json()["wholesale_below_cost"] is False
    assert priced.json()["retail_below_cost"] is True

    stockist_id = await _customer(owner_client, "Suspect Stockist", "Stockist")
    below = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": stockist_id, "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert below.status_code == 201, below.text
    below_line = below.json()["lines"][0]
    assert Decimal(below_line["unit_ex_vat"]) == Decimal("400.00")
    assert below_line["suspect_price_warning"] == (
        "Unit price R400.00 is below average cost R1500.00."
    )

    retail_id = await _customer(owner_client, "Suspect Retail", "Retail")
    placeholder = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": retail_id, "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert placeholder.status_code == 201, placeholder.text
    placeholder_line = placeholder.json()["lines"][0]
    assert Decimal(placeholder_line["unit_ex_vat"]) == Decimal("0.87")
    assert "R1.00 or below" in placeholder_line["suspect_price_warning"]
    assert "R1500.00" in placeholder_line["suspect_price_warning"]

    wholesale_id = await _customer(owner_client, "Suspect Wholesale", "Wholesale")
    healthy = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": wholesale_id, "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert healthy.status_code == 201, healthy.text
    assert Decimal(healthy.json()["lines"][0]["unit_ex_vat"]) == Decimal("2000.00")
    assert healthy.json()["lines"][0]["suspect_price_warning"] is None

    pdf = await owner_client.get(f"/api/v1/quotes/{below.json()['id']}/pdf")
    assert pdf.status_code == 200
    pdf_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages
    )
    assert "average cost" not in pdf_text
    assert "check with the owner" not in pdf_text


async def test_manual_override_still_warns_and_quote_is_not_blocked(
    owner_client: AsyncClient,
) -> None:
    sku = await _sku(owner_client, "SUS-EDIT", retail_ex_vat="2000.00")
    customer_id = await _customer(owner_client, "Suspect Override", "Retail")
    created = await owner_client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "unit_ex_vat": "1.00"}],
        },
    )
    assert created.status_code == 201, created.text
    line = created.json()["lines"][0]
    assert Decimal(line["unit_ex_vat"]) == Decimal("1.00")
    assert "R1.00 or below" in line["suspect_price_warning"]


async def test_restricted_role_sees_the_warning_without_the_cost(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    sku = await _sku(
        owner_client,
        "SUS-HIDE",
        opening_location_id=location_id,
        opening_qty=1,
        opening_cost="1500.00",
        retail_ex_vat="2500.00",
    )
    patched = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"stockist_ex_vat": "400.00"},
    )
    assert patched.status_code == 200, patched.text
    customer_id = await _customer(owner_client, "Suspect Hidden", "Stockist")
    created = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]
    assert "1500.00" in created.json()["lines"][0]["suspect_price_warning"]

    accepted = await owner_client.post(
        f"/api/v1/quotes/{quote_id}/accept",
        json={"hold_stock": False},
    )
    assert accepted.status_code == 200, accepted.text
    order_id = accepted.json()["id"]
    assert "1500.00" in accepted.json()["lines"][0]["suspect_price_warning"]

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-10-27",
            "lines": [
                {
                    "description": "Hidden cost",
                    "qty": 1,
                    "sku_id": sku["id"],
                    "unit_ex_vat": "400.00",
                }
            ],
        },
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]
    assert "1500.00" in invoice.json()["lines"][0]["suspect_price_warning"]

    await _login(async_client, "till@example.com", settings.seed_till_password)
    sku_body = await async_client.get(f"/api/v1/skus/{sku['id']}")
    assert sku_body.status_code == 200, sku_body.text
    assert sku_body.json()["average_unit_cost_zar"] is None
    assert sku_body.json()["stockist_below_cost"] is True
    assert "1500" not in sku_body.text

    quote_body = await async_client.get(f"/api/v1/quotes/{quote_id}")
    assert quote_body.status_code == 200, quote_body.text
    quote_warning = quote_body.json()["lines"][0]["suspect_price_warning"]
    assert quote_warning == RESTRICTED_SUSPECT_PRICE_WARNING
    assert "1500" not in quote_warning

    order_body = await async_client.get(f"/api/v1/orders/{order_id}")
    assert order_body.status_code == 200, order_body.text
    assert (
        order_body.json()["lines"][0]["suspect_price_warning"] == RESTRICTED_SUSPECT_PRICE_WARNING
    )
    assert "1500" not in order_body.json()["lines"][0]["suspect_price_warning"]

    invoice_body = await async_client.get(f"/api/v1/invoices/{invoice_id}")
    assert invoice_body.status_code == 200, invoice_body.text
    assert (
        invoice_body.json()["lines"][0]["suspect_price_warning"] == RESTRICTED_SUSPECT_PRICE_WARNING
    )
    assert "1500" not in invoice_body.json()["lines"][0]["suspect_price_warning"]
    await _relogin_owner(owner_client)


async def test_till_sale_warns_and_still_completes(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    sku = await _sku(
        owner_client,
        "SUS-TILL",
        opening_location_id=bedford_id,
        opening_qty=2,
        opening_cost="1500.00",
        retail_ex_vat="0.87",
    )
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201, sale.text
    line = sale.json()["lines"][0]
    assert Decimal(line["unit_ex_vat"]) == Decimal("0.87")
    assert line["suspect_price_warning"] == RESTRICTED_SUSPECT_PRICE_WARNING
    assert "1500" not in line["suspect_price_warning"]
    await _relogin_owner(owner_client)
