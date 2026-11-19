"""Till return credits are allocated from the monetary snapshot on the invoice."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.test_purchase_orders import _location_id_by_name
from tests.test_sku_bom import _sku
from tests.test_stock_returns import _return_payload


@pytest.mark.parametrize(
    ("return_qty", "net", "vat", "gross"),
    [(3, "271.49", "40.72", "312.21"), (2, "180.99", "27.15", "208.14")],
)
async def test_till_return_preserves_posted_line_rounding(
    owner_client: AsyncClient, return_qty: int, net: str, vat: str, gross: str
) -> None:
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sku = await _sku(
        owner_client,
        "TILL-ROUNDING-RETURN",
        retail_ex_vat="100.55",
        opening_location_id=showroom,
        opening_qty=3,
        opening_cost="25.00",
    )
    response = await owner_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": showroom,
            "lines": [{"sku_id": sku["id"], "qty": 3, "discount_percent": "10"}],
            "tender": "cash",
        },
    )
    assert response.status_code == 201, response.text
    sale = response.json()
    sale_line = sale["lines"][0]
    assert Decimal(sale_line["unit_ex_vat"]) == Decimal("90.50")
    assert Decimal(sale_line["ex_vat"]) == Decimal("271.49")
    assert Decimal(sale_line["vat_amount"]) == Decimal("40.72")
    assert Decimal(sale_line["inc_vat"]) == Decimal("312.21")

    payload = _return_payload(sale["invoice_id"], showroom, sale_line["id"], "write_off")
    repeated = {"invoice_line_id": sale_line["id"], "qty": 2}
    invalid = await owner_client.post("/api/v1/returns", json={**payload, "lines": [repeated] * 2})
    assert invalid.status_code == 400
    assert "Duplicate invoice line" in invalid.json()["detail"]
    invalid = await owner_client.post(
        "/api/v1/returns", json={**payload, "lines": [{**repeated, "qty": 4}]}
    )
    assert invalid.status_code == 400
    assert "Return quantity exceeds invoice line quantity" in invalid.json()["detail"]

    payload["lines"][0]["qty"] = return_qty
    drafted = await owner_client.post("/api/v1/returns", json=payload)
    assert drafted.status_code == 201, drafted.text
    completed = await owner_client.post(f"/api/v1/returns/{drafted.json()['id']}/complete")
    assert completed.status_code == 200, completed.text
    credit = await owner_client.get(f"/api/v1/credit-notes/{completed.json()['credit_note_id']}")
    assert credit.status_code == 200, credit.text
    amounts = credit.json()
    assert Decimal(amounts["subtotal_ex_vat"]) == Decimal(net)
    assert Decimal(amounts["vat_amount"]) == Decimal(vat)
    assert Decimal(amounts["total_inc_vat"]) == Decimal(gross)

    repeated_return = await owner_client.post("/api/v1/returns", json=payload)
    assert repeated_return.status_code == 409
