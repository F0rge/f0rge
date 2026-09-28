"""Paid Storefront imports must remain idempotent and ledger-safe."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.inventory import LocationStock
from app.models.location_bin import BinStock
from app.models.journal import JournalEntry, JournalLine
from app.models.ops_commerce_acknowledgement import OpsCommerceAcknowledgement
from app.models.ops_commerce_order import OpsCommerceOrder
from app.models.sales_order import SalesOrder, SalesOrderPayment
from app.models.tax_invoice import TaxInvoice
from app.models.unit_cost_audit import UnitCostAudit
from app.models.account import Account
from app.models.customer import Customer
from app.models.team import Team
from app.models.user import User


@pytest_asyncio.fixture
async def ops_headers(
    monkeypatch: pytest.MonkeyPatch,
    async_db: AsyncSession,
) -> dict[str, str]:
    company_id = await async_db.scalar(select(Team.id))
    assert company_id is not None
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id), raising=False)
    monkeypatch.setattr(settings, "ops_commerce_token", "storefront-test-token", raising=False)
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test", raising=False)
    return {
        "Authorization": "Bearer storefront-test-token",
        "X-Ops-Company-ID": str(company_id),
    }


async def _paid_order_payload(owner_client: AsyncClient) -> tuple[dict[str, object], str]:
    locations = await owner_client.get("/api/v1/locations")
    location_id = next(row["id"] for row in locations.json() if row["name"] == "Kramerville")
    created = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "STOREFRONT-CHAIR-748",
            "our_barcode": "STOREFRONT-CHAIR-748-BAR",
            "name": "Storefront chair",
            "design": "Storefront chair",
            "fabric": "Oak",
            "opening_location_id": location_id,
            "opening_qty": 2,
            "opening_unit_cost_zar": "100.00",
        },
    )
    assert created.status_code == 201
    sku_id = created.json()["id"]
    assert (
        await owner_client.patch(
            f"/api/v1/skus/{sku_id}",
            json={"retail_inc_vat": "1150.00", "storefront_published": True},
        )
    ).status_code == 200
    return (
        {
            "company_id": "00000000-0000-0000-0000-000000000001",
            "channel": "storefront",
            "external_order_id": "order-748-001",
            "external_payment_id": "payment-748-001",
            "correlation_id": "storefront:order-748-001",
            "currency_code": "ZAR",
            "customer": {
                "external_id": "customer-748-001",
                "name": "Ada Storefront",
                "email": "ada-storefront@example.com",
                "phone": "+27110000001",
                "billing_address": "1 Main Street, Johannesburg, 2000",
            },
            "fulfillment": {
                "type": "delivery",
                "reference": "delivery-748-001",
                "recipient": "Ada Storefront",
                "address": {
                    "address_1": "1 Main Street",
                    "address_2": "Apt 2",
                    "city": "Johannesburg",
                    "province": "Gauteng",
                    "postal_code": "2000",
                    "country_code": "za",
                },
                "fee_ex_minor_zar": 0,
                "fee_vat_minor_zar": 0,
                "fee_total_minor_zar": 0,
            },
            "lines": [
                {
                    "external_line_id": "line-1",
                    "source_sku_id": sku_id,
                    "sku": "STOREFRONT-CHAIR-748",
                    "title": "Storefront chair",
                    "quantity": 1,
                    "unit_ex_minor_zar": 100000,
                    "ex_minor_zar": 100000,
                    "vat_minor_zar": 15000,
                    "total_minor_zar": 115000,
                }
            ],
            "totals": {
                "subtotal_ex_minor_zar": 100000,
                "tax_minor_zar": 15000,
                "delivery_ex_minor_zar": 0,
                "delivery_tax_minor_zar": 0,
                "delivery_total_minor_zar": 0,
                "total_minor_zar": 115000,
            },
            "payment": {
                "provider": "peach",
                "reference": "gateway-ref-748-001",
                "captured_at": "2026-09-28T18:00:00Z",
                "amount_minor_zar": 115000,
                "currency_code": "ZAR",
            },
        },
        sku_id,
    )


@pytest.mark.asyncio
async def test_paid_handoff_posts_external_tender_once_and_acknowledges_stock_after_invoice(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> None:
    payload, sku_id = await _paid_order_payload(owner_client)
    # Bind the body to this isolated operational instance.
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]

    first = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert first.status_code == 201
    imported = first.json()
    assert imported["status"] == "imported"
    handoff_id = imported["id"]

    duplicate = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == handoff_id

    changed = {
        **payload,
        "customer": {**payload["customer"], "phone": "+27119999999"},
        "payment": {**payload["payment"], "reference": "mutated-gateway-reference"},
    }
    conflict = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=changed, headers=ops_headers
    )
    assert conflict.status_code == 409
    accepted = await async_db.scalar(
        select(OpsCommerceOrder).where(OpsCommerceOrder.external_order_id == "order-748-001")
    )
    assert accepted is not None and accepted.gateway_reference == "gateway-ref-748-001"

    assert await async_db.scalar(select(func.count()).select_from(SalesOrder)) == 1
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == 1
    assert await async_db.scalar(select(func.count()).select_from(SalesOrderPayment)) == 0
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.email == "ada-storefront@example.com")
        )
        == 1
    )
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceAcknowledgement)) == 1
    storefront_audit = await async_db.scalar(
        select(UnitCostAudit).where(UnitCostAudit.source == "storefront")
    )
    assert storefront_audit is not None
    assert storefront_audit.changed_by_user_id is not None
    actor = await async_db.get(User, storefront_audit.changed_by_user_id)
    assert actor is not None and actor.email == "storefront-integration@system.example.com"
    assert actor.is_disabled is True and actor.role == "system"
    from app.services.auth import hash_password

    actor.password_hash = hash_password("known-test-password")
    await async_db.flush()
    rejected_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": actor.email, "password": "known-test-password"},
    )
    assert rejected_login.status_code == 401
    from app.services.auth import JWT_COOKIE_NAME, create_access_token

    owner_client.cookies.clear()
    actor_token = create_access_token(actor.id, 1)
    actor_session = await owner_client.get(
        "/api/v1/auth/me", cookies={JWT_COOKIE_NAME: actor_token}
    )
    assert actor_session.status_code == 401
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email == "storefront-integration@system.example.com")
        )
        == 1
    )

    stock = await async_db.scalar(select(LocationStock).where(LocationStock.sku_id == UUID(sku_id)))
    assert stock is not None and stock.on_hand == 1

    imported_payment = await async_db.scalar(
        select(JournalEntry).where(JournalEntry.id == UUID(imported["payment_journal_id"]))
    )
    assert imported_payment is not None
    assert imported_payment.source == "storefront"
    lines = (
        (
            await async_db.execute(
                select(JournalLine).where(JournalLine.entry_id == imported_payment.id)
            )
        )
        .scalars()
        .all()
    )
    balances = {
        account.code: (line.debit_zar, line.credit_zar)
        for line in lines
        for account in [await async_db.get(Account, line.account_id)]
    }
    assert balances["1150"] == (Decimal("1150.00"), Decimal("0.00"))
    assert balances["2300"] == (Decimal("0.00"), Decimal("1150.00"))

    published = await owner_client.get(
        "/api/v1/ops-commerce/v1/products",
        headers=ops_headers,
    )
    assert published.status_code == 200
    assert published.json()["products"][0]["available_quantity"] == 1
    assert published.json()["products"][0]["acknowledged_commitment_ids"] == [
        "storefront:order-748-001:line-1"
    ]


@pytest.mark.asyncio
async def test_paid_handoff_stock_conflict_is_durable_and_retry_acknowledges_only_after_commit(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> None:
    payload, sku_id = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    await async_db.execute(
        LocationStock.__table__.update()
        .where(LocationStock.sku_id == UUID(sku_id))
        .values(on_hand=0)
    )
    await async_db.execute(
        BinStock.__table__.update().where(BinStock.sku_id == UUID(sku_id)).values(on_hand=0)
    )

    response = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert response.status_code == 202
    handoff = response.json()
    assert handoff["status"] == "stock_conflict"
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceAcknowledgement)) == 0
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == 0
    assert await async_db.scalar(select(func.count()).select_from(SalesOrderPayment)) == 0

    await async_db.execute(
        LocationStock.__table__.update()
        .where(LocationStock.sku_id == UUID(sku_id))
        .values(on_hand=1)
    )
    await async_db.execute(
        BinStock.__table__.update().where(BinStock.sku_id == UUID(sku_id)).values(on_hand=1)
    )
    retried = await owner_client.post(f"/api/v1/storefront/orders/{handoff['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "imported"
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == 1
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceAcknowledgement)) == 1
    stock = await async_db.scalar(select(LocationStock).where(LocationStock.sku_id == UUID(sku_id)))
    assert stock is not None and stock.on_hand == 0

    repeated = await owner_client.post(f"/api/v1/storefront/orders/{handoff['id']}/retry")
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "imported"
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == 1
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceAcknowledgement)) == 1


@pytest.mark.asyncio
async def test_paid_handoff_machine_and_staff_routes_enforce_their_own_permissions(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> None:
    payload, _ = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    route = "/api/v1/ops-commerce/v1/orders"

    wrong_token = await owner_client.post(
        route,
        json=payload,
        headers={**ops_headers, "Authorization": "Bearer wrong-instance-token"},
    )
    assert wrong_token.status_code == 401
    wrong_host = await owner_client.post(
        route,
        json=payload,
        headers={**ops_headers, "Host": "another-instance.test"},
    )
    assert wrong_host.status_code == 403
    wrong_header_company = await owner_client.post(
        route,
        json=payload,
        headers={**ops_headers, "X-Ops-Company-ID": str(UUID(int=1))},
    )
    assert wrong_header_company.status_code == 403
    wrong_body_company = await owner_client.post(
        route,
        json={**payload, "company_id": str(UUID(int=2))},
        headers=ops_headers,
    )
    assert wrong_body_company.status_code == 403
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceOrder)) == 0
    assert await async_db.scalar(select(func.count()).select_from(SalesOrder)) == 0
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == 0

    await async_client.post("/api/v1/auth/logout")
    unauthenticated = await async_client.get("/api/v1/storefront/orders")
    assert unauthenticated.status_code == 401
    books_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert books_login.status_code == 200
    forbidden_staff = await async_client.get("/api/v1/storefront/orders")
    assert forbidden_staff.status_code == 403
