"""Paid Storefront imports must remain idempotent and ledger-safe."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from app.models.delivery import DeliveryStatus
from app.models.journal import JournalEntry, JournalLine
from app.models.ops_commerce_acknowledgement import OpsCommerceAcknowledgement
from app.models.ops_commerce_fulfillment_event import OpsCommerceFulfillmentEvent
from app.models.ops_commerce_order import OpsCommerceOrder
from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderPayment, SalesOrderStatus
from app.models.tax_invoice import TaxInvoice
from app.models.unit_cost_audit import UnitCostAudit
from app.models.account import Account
from app.models.customer import Customer
from app.models.team import Team
from app.models.user import User
from app.services.storefront_fulfillment import StorefrontFulfillmentService


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
async def test_mixed_paid_order_imports_awaiting_stock_without_minting_mto_inventory(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> None:
    payload, stocked_sku_id = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    created = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "STOREFRONT-MTO-752",
            "our_barcode": "STOREFRONT-MTO-752-BAR",
            "name": "Made-to-order sofa",
            "design": "Made-to-order sofa",
            "fabric": "Linen",
        },
    )
    assert created.status_code == 201
    mto_sku_id = created.json()["id"]
    now = datetime.now(timezone.utc)
    offer = await owner_client.patch(
        f"/api/v1/skus/{mto_sku_id}",
        json={
            "retail_inc_vat": "1150.00",
            "storefront_published": True,
            "made_to_order_capacity": 3,
            "made_to_order_lead_time_min_days": 28,
            "made_to_order_lead_time_max_days": 42,
            "made_to_order_expires_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert offer.status_code == 200
    accepted_from = (now + timedelta(days=28)).date().isoformat()
    accepted_by = (now + timedelta(days=42)).date().isoformat()
    mto_promise = {
        "kind": "made_to_order",
        "offer_id": offer.json()["made_to_order_offer_id"],
        "min_lead_time_days": 28,
        "max_lead_time_days": 42,
        "estimated_from": accepted_from,
        "estimated_by": accepted_by,
        "expires_at": offer.json()["made_to_order_expires_at"],
    }
    lines = payload["lines"]
    assert isinstance(lines, list)
    lines[0]["fulfillment_promise"] = {
        "kind": "stocked",
        "estimated_from": now.date().isoformat(),
        "estimated_by": now.date().isoformat(),
    }
    lines.append(
        {
            "external_line_id": "line-mto",
            "source_sku_id": mto_sku_id,
            "sku": "STOREFRONT-MTO-752",
            "title": "Made-to-order sofa",
            "quantity": 1,
            "unit_ex_minor_zar": 100000,
            "ex_minor_zar": 100000,
            "vat_minor_zar": 15000,
            "total_minor_zar": 115000,
            "fulfillment_promise": mto_promise,
        }
    )
    payload["fulfillment_promise"] = {
        "version": 1,
        "kind": "mixed",
        "accepted_at": now.isoformat(),
        "estimated_from": accepted_from,
        "estimated_by": accepted_by,
    }
    totals = payload["totals"]
    assert isinstance(totals, dict)
    totals["subtotal_ex_minor_zar"] = 200000
    totals["tax_minor_zar"] = 30000
    totals["total_minor_zar"] = 230000
    payment = payload["payment"]
    assert isinstance(payment, dict)
    payment["amount_minor_zar"] = 230000

    missing_summary = {**payload, "fulfillment_promise": None}
    rejected = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=missing_summary, headers=ops_headers
    )
    assert rejected.status_code == 422

    response = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "imported"
    order = await async_db.get(SalesOrder, UUID(response.json()["sales_order_id"]))
    assert order is not None
    assert order.status == SalesOrderStatus.AWAITING_STOCK
    assert order.awaiting_stock is True
    assert order.fulfillment_promise["estimated_by"] == accepted_by
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == 0
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceAcknowledgement)) == 2
    stocked = await async_db.scalar(
        select(LocationStock).where(LocationStock.sku_id == UUID(stocked_sku_id))
    )
    assert stocked is not None and stocked.on_hand == 1
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(LocationStock)
            .where(LocationStock.sku_id == UUID(mto_sku_id))
        )
        == 0
    )
    duplicate = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == response.json()["id"]
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceAcknowledgement)) == 2


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


@pytest.mark.asyncio
async def test_collection_status_is_staff_mutable_idempotent_and_acknowledged_per_company(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> None:
    payload, _ = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    payload["fulfillment"]["type"] = "collection"
    payload["fulfillment_promise"] = {
        "version": 1,
        "kind": "made_to_order",
        "accepted_at": "2026-09-29T10:00:00Z",
        "estimated_from": "2026-10-13",
        "estimated_by": "2026-10-27",
    }
    payload["lines"][0]["fulfillment_promise"] = {
        "kind": "made_to_order",
        "offer_id": "b45f57d9-e635-4686-8efb-29088c544c3e",
        "min_lead_time_days": 14,
        "max_lead_time_days": 28,
        "estimated_from": "2026-10-13",
        "estimated_by": "2026-10-27",
        "expires_at": "2026-10-01T00:00:00Z",
    }
    created = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert created.status_code == 201
    handoff = created.json()
    assert handoff["fulfillment_status"] == "confirmed"
    assert handoff["fulfillment_promise"] == payload["fulfillment_promise"]
    order = await async_db.scalar(
        select(SalesOrder).where(SalesOrder.fulfillment_promise.is_not(None))
    )
    assert order is not None and order.fulfillment_promise == payload["fulfillment_promise"]
    line = await async_db.scalar(
        select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)
    )
    assert (
        line is not None and line.fulfillment_promise == payload["lines"][0]["fulfillment_promise"]
    )

    status_url = f"/api/v1/storefront/orders/{handoff['id']}/collection-status"
    await async_client.post("/api/v1/auth/logout")
    books_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert books_login.status_code == 200
    forbidden_books = await async_client.patch(status_url, json={"status": "ready_for_collection"})
    assert forbidden_books.status_code == 403

    await owner_client.post("/api/v1/auth/logout")
    owner_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": settings.seed_owner_password},
    )
    assert owner_login.status_code == 200

    ready = await owner_client.patch(status_url, json={"status": "ready_for_collection"})
    assert ready.status_code == 200
    assert ready.json()["fulfillment_status"] == "ready_for_collection"
    revision = ready.json()["fulfillment_revision"]
    repeated_ready = await owner_client.patch(status_url, json={"status": "ready_for_collection"})
    assert repeated_ready.status_code == 200
    assert repeated_ready.json()["fulfillment_revision"] == revision
    collected = await owner_client.patch(status_url, json={"status": "collected"})
    assert collected.status_code == 200
    assert collected.json()["fulfillment_status"] == "collected"
    regressed = await owner_client.patch(status_url, json={"status": "ready_for_collection"})
    assert regressed.status_code == 409
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceFulfillmentEvent)) == 2

    feed_url = "/api/v1/ops-commerce/v1/fulfillment-events"
    feed = await owner_client.get(feed_url, headers=ops_headers)
    assert feed.status_code == 200
    items = feed.json()["items"]
    assert [item["status"] for item in items] == ["ready_for_collection", "collected"]
    assert all(item["fulfillment_promise"] == payload["fulfillment_promise"] for item in items)
    wrong_host = await owner_client.get(
        feed_url, headers={**ops_headers, "Host": "another-instance.test"}
    )
    assert wrong_host.status_code == 403
    wrong_company = await owner_client.get(
        feed_url, headers={**ops_headers, "X-Ops-Company-ID": str(UUID(int=2))}
    )
    assert wrong_company.status_code == 403
    bad_ack = await owner_client.post(
        f"{feed_url}/ack",
        json={"event_ids": [items[0]["event_id"]]},
        headers={**ops_headers, "Authorization": "Bearer wrong-instance-token"},
    )
    assert bad_ack.status_code == 401
    ack = await owner_client.post(
        f"{feed_url}/ack",
        json={"event_ids": [item["event_id"] for item in items]},
        headers=ops_headers,
    )
    assert ack.status_code == 200 and ack.json()["acknowledged"] == 2
    assert (await owner_client.get(feed_url, headers=ops_headers)).json()["items"] == []


@pytest.mark.asyncio
async def test_existing_paid_delivery_can_catch_up_directly_to_completed(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> None:
    payload, _ = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    payload["external_order_id"] = "order-753-existing-delivery"
    payload["external_payment_id"] = "payment-753-existing-delivery"
    payload["correlation_id"] = "storefront:order-753-existing-delivery"
    created = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert created.status_code == 201
    handoff = await async_db.get(OpsCommerceOrder, UUID(created.json()["id"]))
    assert handoff is not None and handoff.fulfillment_status == "confirmed"

    # A delivery packed or loaded before the integration was enabled only emits
    # its next status (for example DELIVERED); catching up must not block staff.
    await StorefrontFulfillmentService(async_db).record_delivery_transition(
        handoff.sales_order_id, DeliveryStatus.DELIVERED
    )
    await async_db.refresh(handoff)
    assert handoff.fulfillment_status == "delivered"
    assert handoff.fulfillment_revision == 1
    event = await async_db.scalar(select(OpsCommerceFulfillmentEvent))
    assert event is not None and event.status == "delivered"
