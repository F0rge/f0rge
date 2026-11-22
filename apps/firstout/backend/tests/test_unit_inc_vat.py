"""Saved lines carry the unit incl. VAT at the document's rate, half-up, as the PDF prints it."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import _location_id_by_name
from tests.test_sku_bom import _sku


async def test_till_sale_and_invoice_lines_return_unit_inc_vat(owner_client: AsyncClient) -> None:
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    # 1739.10 x 1.15 = 1999.965: a cent tie that float rounding in the browser got wrong.
    sku = await _sku(
        owner_client,
        "UNIT-INC-VAT",
        retail_ex_vat="1739.10",
        opening_location_id=showroom,
        opening_qty=1,
        opening_cost="500.00",
    )
    sale = await owner_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": showroom,
            "lines": [{"sku_id": sku["id"], "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["lines"][0]["unit_inc_vat"] == "1999.97"

    invoice = await owner_client.get(f"/api/v1/invoices/{sale.json()['invoice_id']}")
    assert invoice.status_code == 200, invoice.text
    assert invoice.json()["lines"][0]["unit_inc_vat"] == "1999.97"
