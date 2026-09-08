"""V2-S11 outbound deliveries tests."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_till import _set_retail_price, _transfer_to_bedfordview
from tests.test_transfers import _receive_qty_at_location


async def _create_till_user(async_client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-s11-dlv@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    if create_user.status_code == 409:
        pass
    else:
        assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-s11-dlv@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _create_buyer_user(async_client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-s11-dlv@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    if create_user.status_code == 409:
        pass
    else:
        assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-s11-dlv@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _create_warehouse_user(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "warehouse-s11-dlv@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    if create_user.status_code == 409:
        pass
    else:
        assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-s11-dlv@example.com", "password": "warehouse-password"},
    )
    assert login_resp.status_code == 200
    return async_client


async def _paid_till_sale(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
) -> tuple[str, str, str, dict]:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref=our_ref,
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 2)

    till = await _create_till_user(async_client, owner_client)
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
    await _relogin_owner(owner_client)
    return sku_id, bedford_id, body["invoice_id"], body


def _delivery_payload_invoice(invoice_id: str, location_id: str) -> dict:
    return {
        "source_type": "invoice",
        "invoice_id": invoice_id,
        "location_id": location_id,
    }


async def _create_customer(owner_client: AsyncClient) -> str:
    resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Delivery Layby Customer"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _layby_payload(customer_id: str, location_id: str, sku_id: str) -> dict:
    return {
        "customer_id": customer_id,
        "location_id": location_id,
        "due_date": "2026-12-01",
        "hold_stock": True,
        "deposit_amount": "500.00",
        "tender": "cash",
        "lines": [{"sku_id": sku_id, "qty": 1}],
    }


async def test_create_from_paid_invoice(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, sale = await _paid_till_sale(
        async_client,
        owner_client,
        "DLV-PAID",
    )

    created = await owner_client.post(
        "/api/v1/deliveries",
        json=_delivery_payload_invoice(invoice_id, bedford_id),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["delivery_number"] == "DLV-0001"
    assert body["status"] == "draft"
    assert body["source_type"] == "invoice"
    assert len(body["lines"]) == len(sale["lines"])
    assert body["lines"][0]["qty"] == sale["lines"][0]["qty"]


async def test_unpaid_invoice_rejected(
    owner_client: AsyncClient,
) -> None:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Unpaid Delivery Customer"},
    )
    assert customer_resp.status_code == 201
    invoice_resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Consulting", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")

    created = await owner_client.post(
        "/api/v1/deliveries",
        json=_delivery_payload_invoice(invoice["id"], bedford_id),
    )
    assert created.status_code == 400
    assert created.json()["detail"] == "Invoice is not fully paid"


async def test_second_active_delivery_same_invoice_conflicts(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, _ = await _paid_till_sale(
        async_client,
        owner_client,
        "DLV-DUP",
    )
    payload = _delivery_payload_invoice(invoice_id, bedford_id)

    first = await owner_client.post("/api/v1/deliveries", json=payload)
    assert first.status_code == 201

    second = await owner_client.post("/api/v1/deliveries", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Delivery already exists for this invoice"


async def test_pack_then_complete_sets_delivered_and_date(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, _ = await _paid_till_sale(
        async_client,
        owner_client,
        "DLV-COMPLETE",
    )

    created = await owner_client.post(
        "/api/v1/deliveries",
        json=_delivery_payload_invoice(invoice_id, bedford_id),
    )
    assert created.status_code == 201
    delivery_id = created.json()["id"]

    packed = await owner_client.post(f"/api/v1/deliveries/{delivery_id}/pack")
    assert packed.status_code == 200
    assert packed.json()["status"] == "packed"

    completed = await owner_client.post(
        f"/api/v1/deliveries/{delivery_id}/complete",
        json={"delivery_date": "2026-09-15"},
    )
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "delivered"
    assert body["delivery_date"] == "2026-09-15"


async def test_cancel_draft_allows_new_delivery(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, _ = await _paid_till_sale(
        async_client,
        owner_client,
        "DLV-CANCEL",
    )
    payload = _delivery_payload_invoice(invoice_id, bedford_id)

    created = await owner_client.post("/api/v1/deliveries", json=payload)
    assert created.status_code == 201
    delivery_id = created.json()["id"]

    cancelled = await owner_client.post(f"/api/v1/deliveries/{delivery_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    again = await owner_client.post("/api/v1/deliveries", json=payload)
    assert again.status_code == 201


async def test_cancel_packed_rejected(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, _ = await _paid_till_sale(
        async_client,
        owner_client,
        "DLV-NOCANCEL",
    )

    created = await owner_client.post(
        "/api/v1/deliveries",
        json=_delivery_payload_invoice(invoice_id, bedford_id),
    )
    assert created.status_code == 201
    delivery_id = created.json()["id"]

    packed = await owner_client.post(f"/api/v1/deliveries/{delivery_id}/pack")
    assert packed.status_code == 200

    cancelled = await owner_client.post(f"/api/v1/deliveries/{delivery_id}/cancel")
    assert cancelled.status_code == 409
    assert cancelled.json()["detail"] == "Delivery is not a draft"


async def test_create_from_open_layby(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="DLV-LAYBY",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 2)
    customer_id = await _create_customer(owner_client)

    till = await _create_till_user(async_client, owner_client)
    layby = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id),
    )
    assert layby.status_code == 201
    layby_id = layby.json()["id"]

    await _relogin_owner(owner_client)
    created = await owner_client.post(
        "/api/v1/deliveries",
        json={
            "source_type": "layby",
            "layby_id": layby_id,
            "location_id": bedford_id,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["source_type"] == "layby"
    assert body["layby_id"] == layby_id
    assert body["invoice_id"] is None
    assert len(body["lines"]) == 1
    assert body["lines"][0]["sku_id"] == sku_id


async def test_buyer_forbidden_warehouse_pack_unauthenticated(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, _ = await _paid_till_sale(
        async_client,
        owner_client,
        "DLV-ROLE",
    )
    payload = _delivery_payload_invoice(invoice_id, bedford_id)

    buyer = await _create_buyer_user(async_client, owner_client)
    forbidden = await buyer.post("/api/v1/deliveries", json=payload)
    assert forbidden.status_code == 403

    await _relogin_owner(owner_client)
    created = await owner_client.post("/api/v1/deliveries", json=payload)
    assert created.status_code == 201
    delivery_id = created.json()["id"]

    warehouse = await _create_warehouse_user(async_client, owner_client)
    packed = await warehouse.post(f"/api/v1/deliveries/{delivery_id}/pack")
    assert packed.status_code == 200

    async_client.cookies.clear()
    unauth = await async_client.post("/api/v1/deliveries", json=payload)
    assert unauth.status_code == 401


async def test_complete_from_draft_rejected(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    _, bedford_id, invoice_id, _ = await _paid_till_sale(
        async_client,
        owner_client,
        "DLV-SKIPPACK",
    )

    created = await owner_client.post(
        "/api/v1/deliveries",
        json=_delivery_payload_invoice(invoice_id, bedford_id),
    )
    assert created.status_code == 201
    delivery_id = created.json()["id"]

    completed = await owner_client.post(f"/api/v1/deliveries/{delivery_id}/complete", json={})
    assert completed.status_code == 409
    assert completed.json()["detail"] == "Delivery is not packed"
