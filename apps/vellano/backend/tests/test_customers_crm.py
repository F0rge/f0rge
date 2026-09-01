"""V2-S10 customers CRM tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from tests.test_laybys import _layby_payload, _stocked_sku_at_bedford
from tests.test_purchase_orders import _relogin_owner


async def _create_role_client(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    *,
    email: str,
    password: str,
    role: str,
) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={"email": email, "password": password, "role": role},
    )
    if create_user.status_code != 409:
        assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    return async_client


async def test_create_trade_customer_list_includes_crm_fields(owner_client: AsyncClient) -> None:
    created = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "CRM Trade Co S10",
            "email": "trade-s10-crm@example.com",
            "phone": "+27110000000",
            "customer_type": "trade",
            "price_tier": "gold",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["customer_type"] == "trade"
    assert body["price_tier"] == "gold"
    assert body["phone"] == "+27110000000"
    assert body["open_invoices_count"] == 0
    assert body["open_invoices_zar"] == "0.00"
    assert body["active_laybys_count"] == 0
    assert body["active_laybys_zar"] == "0.00"

    listed = await owner_client.get("/api/v1/customers")
    assert listed.status_code == 200
    match = next(c for c in listed.json() if c["name"] == "CRM Trade Co S10")
    assert match["customer_type"] == "trade"
    assert match["price_tier"] == "gold"
    assert match["phone"] == "+27110000000"


async def test_unpaid_invoice_increases_open_invoices_zar(owner_client: AsyncClient) -> None:
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Invoice Customer S10"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Sofa", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert invoice.status_code == 201

    detail = await owner_client.get(f"/api/v1/customers/{customer_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["open_invoices_count"] == 1
    assert Decimal(body["open_invoices_zar"]) == Decimal("1150.00")
    assert body["overdue_invoices_count"] == 0


async def test_overdue_invoice_increments_overdue_count(owner_client: AsyncClient) -> None:
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Overdue Customer S10"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    overdue_date = (date.today() - timedelta(days=31)).isoformat()

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": overdue_date,
            "lines": [{"description": "Chair", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert invoice.status_code == 201

    detail = await owner_client.get(f"/api/v1/customers/{customer_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["open_invoices_count"] == 1
    assert Decimal(body["open_invoices_zar"]) == Decimal("575.00")
    assert body["overdue_invoices_count"] == 1


async def test_new_customer_has_zero_active_laybys(owner_client: AsyncClient) -> None:
    created = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM No Layby Customer S10"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["active_laybys_count"] == 0
    assert body["active_laybys_zar"] == "0.00"


async def test_open_layby_increments_active_laybys_count(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "CRM-LB-S10",
    )
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Layby Customer S10"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    till = await _create_role_client(
        async_client,
        owner_client,
        email="till-s10-crm@example.com",
        password="till-password",
        role="till",
    )
    layby = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer_id, bedford_id, sku_id, hold_stock=False, deposit="100.00"),
    )
    assert layby.status_code == 201

    detail = await owner_client.get(f"/api/v1/customers/{customer_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["active_laybys_count"] == 1
    assert Decimal(body["active_laybys_zar"]) == Decimal("1050.00")


async def test_buyer_cannot_post_customer(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    buyer = await _create_role_client(
        async_client,
        owner_client,
        email="buyer-s10-crm@example.com",
        password="buyer-password",
        role="buyer",
    )
    resp = await buyer.post(
        "/api/v1/customers",
        json={"name": "Buyer Blocked Customer S10"},
    )
    assert resp.status_code == 403


async def test_till_can_post_customer(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    till = await _create_role_client(
        async_client,
        owner_client,
        email="till-s10-crm@example.com",
        password="till-password",
        role="till",
    )
    resp = await till.post(
        "/api/v1/customers",
        json={"name": "Till Created Customer S10"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Till Created Customer S10"


async def test_patch_customer_name_and_type(owner_client: AsyncClient) -> None:
    created = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Patch Before S10", "customer_type": "retail"},
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]

    patched = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"name": "CRM Patch After S10", "customer_type": "trade"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["name"] == "CRM Patch After S10"
    assert body["customer_type"] == "trade"
