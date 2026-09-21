"""Sales order hold, cash/EFT deposits on 2300, remainder invoice."""

from __future__ import annotations

from decimal import Decimal

from typing import Optional

from httpx import AsyncClient

from tests.test_ledger_accounts import _account_balance
from tests.test_purchase_orders import _location_id_by_name
from tests.test_quotes import _named_customer
from tests.test_till import _inventory_on_hand, _set_retail_price
from tests.test_transfers import _receive_qty_at_location


async def _open_held_order(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
    *,
    qty: int = 2,
    hold_qty: int = 1,
    deposit: Optional[str] = "575.00",
) -> dict:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=qty,
        location_name="Kramerville",
        our_ref=our_ref,
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    customer_id = await _named_customer(owner_client, f"SO {our_ref}")
    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": hold_qty}]},
    )
    assert quote.status_code == 201, quote.text
    body: dict = {
        "location_id": location_id,
        "hold_stock": True,
    }
    if deposit is not None:
        body["deposit"] = {"amount": deposit, "tender": "eft"}
    accepted = await owner_client.post(f"/api/v1/quotes/{quote.json()['id']}/accept", json=body)
    assert accepted.status_code == 200, accepted.text
    order = accepted.json()
    order["_sku_id"] = sku_id
    order["_location_id"] = location_id
    order["_on_hand_before"] = qty
    return order


async def test_accept_eft_drops_warehouse_on_hand(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    order = await _open_held_order(async_client, owner_client, "SO-HOLD", deposit="575.00")
    on_hand = await _inventory_on_hand(owner_client, order["_sku_id"], order["_location_id"])
    assert on_hand == 1
    assert Decimal(order["amount_paid"]) == Decimal("575.00")
    assert Decimal(order["balance"]) == Decimal("575.00")
    assert order["payments"][0]["tender"] == "eft"


async def test_cancel_restocks_and_refunds_deposits(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    deposits_before = Decimal(await _account_balance(owner_client, "2300"))
    order = await _open_held_order(async_client, owner_client, "SO-CANCEL", deposit="575.00")
    cancelled = await owner_client.post(f"/api/v1/orders/{order['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    on_hand = await _inventory_on_hand(owner_client, order["_sku_id"], order["_location_id"])
    assert on_hand == 2
    deposits_after = Decimal(await _account_balance(owner_client, "2300"))
    assert deposits_after == deposits_before


async def test_remainder_invoice_half_ar_held_stock_unchanged(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    deposits_before = Decimal(await _account_balance(owner_client, "2300"))
    ar_before = Decimal(await _account_balance(owner_client, "1200"))
    order = await _open_held_order(async_client, owner_client, "SO-REMAINDER", deposit="575.00")
    on_hand_held = await _inventory_on_hand(owner_client, order["_sku_id"], order["_location_id"])
    invoiced = await owner_client.post(f"/api/v1/orders/{order['id']}/invoice")
    assert invoiced.status_code == 200, invoiced.text
    body = invoiced.json()
    assert body["status"] == "invoiced"
    assert body["invoice_id"] is not None
    invoice = await owner_client.get(f"/api/v1/invoices/{body['invoice_id']}")
    assert invoice.status_code == 200
    inv = invoice.json()
    assert Decimal(inv["total_inc_vat"]) == Decimal("1150.00")
    assert Decimal(inv["amount_paid"]) == Decimal("575.00")
    on_hand_after = await _inventory_on_hand(owner_client, order["_sku_id"], order["_location_id"])
    assert on_hand_after == on_hand_held
    deposits_after = Decimal(await _account_balance(owner_client, "2300"))
    ar_after = Decimal(await _account_balance(owner_client, "1200"))
    assert deposits_after == deposits_before
    assert ar_after - ar_before == Decimal("575.00")
