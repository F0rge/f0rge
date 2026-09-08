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
    assert body["overdue_invoices_zar"] == "0.00"
    assert body["last_purchase_date"] is None
    assert body["credit_limit"] is None
    assert body["on_hold"] is False
    assert body["on_hold_reason"] is None
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
    assert Decimal(body["overdue_invoices_zar"]) == Decimal("0.00")
    assert body["last_purchase_date"] == "2026-09-01"


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
    assert Decimal(body["overdue_invoices_zar"]) == Decimal("575.00")
    assert body["last_purchase_date"] == overdue_date


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


async def test_overdue_clears_after_payment(owner_client: AsyncClient) -> None:
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Overdue Pay Clear F6"},
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

    paid = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice.json()["id"],
            "amount": "575.00",
            "currency": "ZAR",
            "paid_on": date.today().isoformat(),
        },
    )
    assert paid.status_code == 201

    detail = await owner_client.get(f"/api/v1/customers/{customer_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["open_invoices_count"] == 0
    assert body["overdue_invoices_count"] == 0
    assert Decimal(body["overdue_invoices_zar"]) == Decimal("0.00")
    assert body["last_purchase_date"] == overdue_date


async def test_list_filters_overdue_active_layby_on_hold(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    overdue = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Filter Overdue F6"},
    )
    held = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Filter Hold F6"},
    )
    layby_customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Filter Layby F6"},
    )
    assert overdue.status_code == 201
    assert held.status_code == 201
    assert layby_customer.status_code == 201

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": overdue.json()["id"],
            "issue_date": (date.today() - timedelta(days=31)).isoformat(),
            "lines": [{"description": "Ottoman", "qty": 1, "unit_ex_vat": "200.00"}],
        },
    )
    assert invoice.status_code == 201

    hold_patch = await owner_client.patch(
        f"/api/v1/customers/{held.json()['id']}",
        json={"on_hold": True, "on_hold_reason": "account review"},
    )
    assert hold_patch.status_code == 200

    sku_id, bedford_id = await _stocked_sku_at_bedford(
        async_client,
        owner_client,
        "CRM-FILT-LB-F6",
    )
    till = await _create_role_client(
        async_client,
        owner_client,
        email="till-s10-crm@example.com",
        password="till-password",
        role="till",
    )
    layby = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(
            layby_customer.json()["id"],
            bedford_id,
            sku_id,
            hold_stock=False,
            deposit="100.00",
        ),
    )
    assert layby.status_code == 201

    overdue_list = await till.get("/api/v1/customers", params={"overdue": True})
    assert overdue_list.status_code == 200
    overdue_names = {row["name"] for row in overdue_list.json()}
    assert "CRM Filter Overdue F6" in overdue_names
    assert "CRM Filter Hold F6" not in overdue_names
    assert "CRM Filter Layby F6" not in overdue_names

    hold_list = await till.get("/api/v1/customers", params={"on_hold": True})
    assert hold_list.status_code == 200
    hold_names = {row["name"] for row in hold_list.json()}
    assert hold_names == {"CRM Filter Hold F6"}

    layby_list = await till.get("/api/v1/customers", params={"active_layby": True})
    assert layby_list.status_code == 200
    layby_names = {row["name"] for row in layby_list.json()}
    assert "CRM Filter Layby F6" in layby_names
    assert "CRM Filter Overdue F6" not in layby_names

    and_list = await till.get(
        "/api/v1/customers",
        params={"overdue": True, "on_hold": True},
    )
    assert and_list.status_code == 200
    assert and_list.json() == []


async def test_till_cannot_patch_credit_limit(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    created = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Till Credit Block F6"},
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]

    till = await _create_role_client(
        async_client,
        owner_client,
        email="till-s10-crm@example.com",
        password="till-password",
        role="till",
    )
    profile = await till.patch(
        f"/api/v1/customers/{customer_id}",
        json={"phone": "+27112223333"},
    )
    assert profile.status_code == 200
    assert profile.json()["phone"] == "+27112223333"

    credit = await till.patch(
        f"/api/v1/customers/{customer_id}",
        json={"credit_limit": "5000.00"},
    )
    assert credit.status_code == 403


async def test_owner_and_buyer_can_patch_credit_fields(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    created = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Credit Patch F6"},
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]

    owner_patch = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={
            "credit_limit": "2500.00",
            "on_hold": True,
            "on_hold_reason": "terms review",
        },
    )
    assert owner_patch.status_code == 200
    assert Decimal(owner_patch.json()["credit_limit"]) == Decimal("2500.00")
    assert owner_patch.json()["on_hold"] is True
    assert owner_patch.json()["on_hold_reason"] == "terms review"

    buyer = await _create_role_client(
        async_client,
        owner_client,
        email="buyer-s10-crm@example.com",
        password="buyer-password",
        role="buyer",
    )
    buyer_patch = await buyer.patch(
        f"/api/v1/customers/{customer_id}",
        json={"on_hold": False, "on_hold_reason": None, "credit_limit": "3000.00"},
    )
    assert buyer_patch.status_code == 200
    assert buyer_patch.json()["on_hold"] is False
    assert buyer_patch.json()["on_hold_reason"] is None
    assert Decimal(buyer_patch.json()["credit_limit"]) == Decimal("3000.00")

    name_blocked = await buyer.patch(
        f"/api/v1/customers/{customer_id}",
        json={"name": "Buyer Cannot Rename F6"},
    )
    assert name_blocked.status_code == 403


async def test_books_invoice_on_hold_conflicts(owner_client: AsyncClient) -> None:
    created = await owner_client.post(
        "/api/v1/customers",
        json={"name": "CRM Invoice Hold F6"},
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]
    held = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"on_hold": True},
    )
    assert held.status_code == 200

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": date.today().isoformat(),
            "lines": [{"description": "Lamp", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert invoice.status_code == 409
    assert invoice.json()["detail"] == "Customer is on hold"
