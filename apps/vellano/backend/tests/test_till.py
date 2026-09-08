"""S9 till sale tests."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from tests.test_purchase_orders import (
    _create_buyer,
    _create_sku,
    _create_supplier,
    _create_till,
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_transfers import _receive_qty_at_location, complete_location_transfer


async def _set_retail_price(client: AsyncClient, sku_id: str, retail_ex: str) -> None:
    resp = await client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": retail_ex},
    )
    assert resp.status_code == 200


async def _inventory_on_hand(
    client: AsyncClient,
    sku_id: str,
    location_id: str,
) -> int:
    inv = await client.get("/api/v1/inventory")
    assert inv.status_code == 200
    row = next(item for item in inv.json() if item["sku_id"] == sku_id)
    loc = next(loc for loc in row["locations"] if loc["location_id"] == location_id)
    return loc["on_hand"]


async def _login_warehouse(client: AsyncClient) -> AsyncClient:
    client.cookies.clear()
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-po@example.com", "password": "warehouse-password"},
    )
    assert login_resp.status_code == 200
    return client


async def _transfer_to_bedfordview(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    sku_id: str,
    qty: int,
) -> str:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _login_warehouse(async_client)
    await _relogin_owner(owner_client)
    await complete_location_transfer(
        warehouse,
        kramerville_id,
        bedford_id,
        sku_id,
        qty,
    )
    return bedford_id


async def test_till_cash_sale_decrements_bedfordview_stock(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="TILL-CASH",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 2)

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
    body = sale.json()
    assert body["tender"] == "cash"
    assert body["invoice_number"].startswith("INV-")
    assert body["payment_number"].startswith("PAY-")
    assert body["vat_amount"] == "150.00"
    assert body["subtotal_ex_vat"] == "1000.00"
    assert body["total_inc_vat"] == "1150.00"
    assert body["location"]["on_hand"] == 1

    on_hand = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert on_hand == 1

    invoice = await owner_client.get(f"/api/v1/invoices/{body['invoice_id']}")
    assert invoice.status_code == 200
    payload = invoice.json()
    assert payload["balance"] == "0.00"
    assert payload["lines"][0]["sku_id"] == sku_id


async def test_till_card_sale_records_tender(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-CARD",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "500.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "card",
        },
    )
    assert sale.status_code == 201
    assert sale.json()["tender"] == "card"

    payments = await owner_client.get("/api/v1/payments")
    assert payments.status_code == 200
    payment = next(p for p in payments.json() if p["id"] == sale.json()["payment_id"])
    assert payment["tender"] == "card"


async def test_till_cannot_sell_on_water(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Till Water Supplier")
    sku = await _create_sku(
        owner_client,
        "TILL-WATER",
        "TILL-WATER-BAR",
        "Water Item",
        "Water Design",
        "Water Fabric",
    )
    await _set_retail_price(owner_client, sku["id"], "100.00")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "50.00"}],
        },
    )
    assert po_resp.status_code == 201
    po_id = po_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku["id"], "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 409

    invoices = await owner_client.get("/api/v1/invoices")
    assert invoices.status_code == 200
    assert len(invoices.json()) == 0


async def test_till_cannot_sell_at_warehouse(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-WH",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "200.00")
    kramerville_id = data["location_id"]

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": kramerville_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 409


async def test_buyer_cannot_create_till_sale(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-BUYER",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "300.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    buyer = await _create_buyer(async_client, owner_client)
    sale = await buyer.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 403


async def test_till_sale_posts_ledger_entries(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-LEDGER",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    accounts_before = await owner_client.get("/api/v1/accounts")
    assert accounts_before.status_code == 200
    balances_before = {a["code"]: Decimal(a["balance_zar"]) for a in accounts_before.json()}

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

    accounts_after = await owner_client.get("/api/v1/accounts")
    balances_after = {a["code"]: Decimal(a["balance_zar"]) for a in accounts_after.json()}

    assert balances_after["1100"] > balances_before["1100"]
    assert balances_after["4000"] < balances_before["4000"]
    assert balances_after["2200"] < balances_before["2200"]


async def test_till_line_discount_reduces_subtotal(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-DISC",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "10"}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201
    body = sale.json()
    assert body["subtotal_ex_vat"] == "900.00"
    assert body["vat_amount"] == "135.00"
    assert body["total_inc_vat"] == "1035.00"


async def test_till_deposit_tender_records_payment_tender(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-DEP",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "500.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "deposit",
        },
    )
    assert sale.status_code == 201
    assert sale.json()["tender"] == "deposit"

    payments = await owner_client.get("/api/v1/payments")
    assert payments.status_code == 200
    payment = next(p for p in payments.json() if p["id"] == sale.json()["payment_id"])
    assert payment["tender"] == "deposit"


async def test_till_full_discount_rejected(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-FULL-DISC",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "400.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "100"}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 400
    assert sale.json()["detail"] == "Sale total must be positive"


async def test_till_eft_sale_records_tender(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-EFT",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "500.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "eft",
        },
    )
    assert sale.status_code == 201
    assert sale.json()["tender"] == "eft"

    payments = await owner_client.get("/api/v1/payments")
    assert payments.status_code == 200
    payment = next(p for p in payments.json() if p["id"] == sale.json()["payment_id"])
    assert payment["tender"] == "eft"


async def test_till_optional_customer_id_attaches_customer(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-CUST",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "400.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Till CRM Customer"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
            "customer_id": customer_id,
        },
    )
    assert sale.status_code == 201

    invoice = await owner_client.get(f"/api/v1/invoices/{sale.json()['invoice_id']}")
    assert invoice.status_code == 200
    payload = invoice.json()
    assert payload["customer_id"] == customer_id
    assert payload["customer_name"] == "Till CRM Customer"


async def test_till_omit_customer_id_uses_walk_in(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="TILL-WALK",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "300.00")
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

    invoice = await owner_client.get(f"/api/v1/invoices/{sale.json()['invoice_id']}")
    assert invoice.status_code == 200
    assert invoice.json()["customer_name"] == WALK_IN_CUSTOMER_NAME


async def test_till_carton_count_decrements_sellable_units(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="TILL-CARTON",
    )
    sku_id = data["sku"]["id"]
    patch = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": "4000.00", "carton_count": 3},
    )
    assert patch.status_code == 200
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 2)

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
    on_hand = await _inventory_on_hand(owner_client, sku_id, bedford_id)
    assert on_hand == 1


async def _ready_showroom_sale(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
    retail_ex: str = "1000.00",
) -> tuple[str, str]:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref=our_ref,
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, retail_ex)
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)
    return sku_id, bedford_id


async def test_till_on_hold_customer_conflicts(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-HOLD-F6")
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Till Hold Customer F6"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    held = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"on_hold": True, "on_hold_reason": "collections"},
    )
    assert held.status_code == 200

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
            "customer_id": customer_id,
        },
    )
    assert sale.status_code == 409
    assert sale.json()["detail"] == "Customer is on hold"


async def test_till_over_credit_limit_conflicts(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-LIMIT-F6")
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Till Limit Customer F6"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    limited = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"credit_limit": "100.00"},
    )
    assert limited.status_code == 200

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
            "customer_id": customer_id,
        },
    )
    assert sale.status_code == 409
    assert sale.json()["detail"] == "Customer exceeds credit limit"


async def test_till_credit_override_owner_records_books_note(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-OVR-F6")
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Till Override Customer F6"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    held = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"on_hold": True, "credit_limit": "50.00"},
    )
    assert held.status_code == 200

    await _relogin_owner(owner_client)
    sale = await owner_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
            "customer_id": customer_id,
            "credit_override": True,
            "credit_override_reason": "manager approved",
        },
    )
    assert sale.status_code == 201
    invoice_id = sale.json()["invoice_id"]

    events = await owner_client.get(
        "/api/v1/books-events",
        params={"document_type": "invoice", "document_id": invoice_id},
    )
    assert events.status_code == 200
    created = next(row for row in events.json() if row["action"] == "created")
    assert created["note"] == "credit override: manager approved"


async def test_till_role_cannot_credit_override(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-OVR403-F6")
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Till Override Block F6"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    held = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"on_hold": True},
    )
    assert held.status_code == 200

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
            "customer_id": customer_id,
            "credit_override": True,
            "credit_override_reason": "please",
        },
    )
    assert sale.status_code == 403

    missing_reason = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
            "customer_id": customer_id,
            "credit_override": True,
        },
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"] == "credit_override_reason is required"


async def test_no_psp_client_in_codebase() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    forbidden = ("stripe", "payfast", "yoco")
    for path in root.rglob("*.py"):
        text = path.read_text().lower()
        for term in forbidden:
            assert term not in text, f"PSP client reference {term!r} found in {path}"
