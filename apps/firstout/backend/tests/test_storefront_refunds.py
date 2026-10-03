from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncio
import asyncpg
import pytest
import pytest_asyncio
from typing import Optional
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from f0rge_testing import async_url

from app.config import settings
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.database import Base, get_db
from app.main import app
from app.models.account import Account
from app.models.credit_note import CreditNote
from app.models.inventory import LocationStock
from app.models.journal import JournalEntry, JournalLine
from app.models.location import Location
from app.models.ops_commerce_order import OpsCommerceOrder
from app.models.ops_commerce_refund import OpsCommerceRefund, OpsCommerceRefundEvent
from app.models.sales_order import SalesOrder
from app.models.stock_return import StockReturnDisposition, StockReturnStatus
from app.models.team import Team
from app.models.user import User
from app.services.auth import hash_password
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService
from app.services.role_user_seed import RoleUserSeedService
from app.services.roles import RoleSeedService
from app.services.storefront_system_actor import StorefrontSystemActorService
from app.services.till_seed import TillSeedService
from app.services.users import BootstrapService
from tests.test_ops_commerce_orders import _paid_order_payload


@pytest_asyncio.fixture
async def refund_ops_headers(
    monkeypatch: pytest.MonkeyPatch,
    async_db: AsyncSession,
) -> dict[str, str]:
    company_id = await async_db.scalar(select(Team.id))
    assert company_id is not None
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id), raising=False)
    monkeypatch.setattr(
        settings, "ops_commerce_token", "storefront-refund-test-token", raising=False
    )
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test", raising=False)
    return {
        "Authorization": "Bearer storefront-refund-test-token",
        "X-Ops-Company-ID": str(company_id),
    }


async def _import_uninvoiced_handoff(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> tuple[dict[str, object], OpsCommerceOrder]:
    payload, _ = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    line = payload["lines"][0]
    now = datetime.now(timezone.utc)
    offer_resp = await owner_client.patch(
        f"/api/v1/skus/{line['source_sku_id']}",
        json={
            "storefront_published": True,
            "made_to_order_capacity": 3,
            "made_to_order_lead_time_min_days": 28,
            "made_to_order_lead_time_max_days": 42,
            "made_to_order_expires_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert offer_resp.status_code == 200
    estimated_from = (now + timedelta(days=28)).date().isoformat()
    estimated_by = (now + timedelta(days=42)).date().isoformat()
    promise = {
        "kind": "made_to_order",
        "offer_id": offer_resp.json()["made_to_order_offer_id"],
        "min_lead_time_days": 28,
        "max_lead_time_days": 42,
        "estimated_from": estimated_from,
        "estimated_by": estimated_by,
        "expires_at": offer_resp.json()["made_to_order_expires_at"],
    }
    line["fulfillment_promise"] = promise
    payload["fulfillment_promise"] = {
        "version": 1,
        "kind": "made_to_order",
        "accepted_at": now.isoformat(),
        "estimated_from": estimated_from,
        "estimated_by": estimated_by,
    }
    response = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "imported"
    assert response.json()["lines"] == [
        {
            "external_line_id": "line-1",
            "title": "Storefront chair",
            "sku": "STOREFRONT-CHAIR-748",
            "quantity": 1,
            "unit_ex_minor_zar": 100000,
            "total_minor_zar": 115000,
        }
    ]
    handoff = await async_db.get(OpsCommerceOrder, UUID(response.json()["id"]))
    assert handoff is not None
    order = await async_db.get(SalesOrder, handoff.sales_order_id)
    assert order is not None and order.invoice_id is None
    return payload, handoff


async def _import_stocked_handoff(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> tuple[dict[str, object], OpsCommerceOrder, str]:
    payload, sku_id = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    response = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert response.status_code == 201
    handoff = await async_db.get(OpsCommerceOrder, UUID(response.json()["id"]))
    assert handoff is not None
    return payload, handoff, sku_id


async def _import_mixed_uninvoiced_handoff(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    ops_headers: dict[str, str],
) -> tuple[dict[str, object], OpsCommerceOrder, str]:
    payload, stocked_sku_id = await _paid_order_payload(owner_client)
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    now = datetime.now(timezone.utc)
    created = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "STOREFRONT-MTO-REFUND-754",
            "our_barcode": "STOREFRONT-MTO-REFUND-754-BAR",
            "name": "Storefront made-to-order refund sofa",
            "design": "Storefront made-to-order refund sofa",
            "fabric": "Linen",
        },
    )
    assert created.status_code == 201
    mto_sku_id = created.json()["id"]
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
    estimated_from = (now + timedelta(days=28)).date().isoformat()
    estimated_by = (now + timedelta(days=42)).date().isoformat()
    stocked_promise = {
        "kind": "stocked",
        "estimated_from": now.date().isoformat(),
        "estimated_by": now.date().isoformat(),
    }
    mto_promise = {
        "kind": "made_to_order",
        "offer_id": offer.json()["made_to_order_offer_id"],
        "min_lead_time_days": 28,
        "max_lead_time_days": 42,
        "estimated_from": estimated_from,
        "estimated_by": estimated_by,
        "expires_at": offer.json()["made_to_order_expires_at"],
    }
    lines = payload["lines"]
    assert isinstance(lines, list)
    lines[0]["fulfillment_promise"] = stocked_promise
    lines.append(
        {
            "external_line_id": "line-mto",
            "source_sku_id": mto_sku_id,
            "sku": "STOREFRONT-MTO-REFUND-754",
            "title": "Storefront made-to-order refund sofa",
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
        "estimated_from": estimated_from,
        "estimated_by": estimated_by,
    }
    totals = payload["totals"]
    assert isinstance(totals, dict)
    totals["subtotal_ex_minor_zar"] = 200000
    totals["tax_minor_zar"] = 30000
    totals["total_minor_zar"] = 230000
    payment = payload["payment"]
    assert isinstance(payment, dict)
    payment["amount_minor_zar"] = 230000
    response = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "imported"
    handoff = await async_db.get(OpsCommerceOrder, UUID(response.json()["id"]))
    assert handoff is not None
    return payload, handoff, stocked_sku_id


def _provider_event(
    *,
    provider_refund_id: str,
    capture_id: str,
    amount_minor: int,
    request_id: Optional[str] = None,
    canonical: Optional[str] = None,
) -> dict[str, object]:
    canonical_sha256 = hashlib.sha256(
        (canonical or f"{provider_refund_id}:{capture_id}:{amount_minor}").encode()
    ).hexdigest()
    return {
        "request_id": request_id,
        "provider_refund_id": provider_refund_id,
        "event_source": "response",
        "referenced_capture_id": capture_id,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "amount_minor": amount_minor,
        "currency_code": "ZAR",
        "result_code": "000.000.000",
        "outcome": "succeeded",
        "canonical_sha256": canonical_sha256,
        "signature_verified": True,
    }


@pytest.mark.asyncio
async def test_books_refund_command_records_verified_partial_refund_once(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    payload, handoff = await _import_uninvoiced_handoff(owner_client, async_db, refund_ops_headers)
    books_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert books_login.status_code == 200

    handoffs = await async_client.get("/api/v1/storefront/orders")
    assert handoffs.status_code == 200
    assert handoffs.json()["items"][0]["lines"][0]["external_line_id"] == "line-1"
    idempotency_key = str(uuid4())
    requested = await async_client.post(
        f"/api/v1/storefront/orders/{handoff.id}/refunds",
        json={"idempotency_key": idempotency_key, "amount_minor": 57500},
    )
    assert requested.status_code == 200
    request_id = requested.json()["id"]
    assert requested.json()["status"] == "requested"

    status = await async_client.get(f"/api/v1/storefront/orders/{handoff.id}/refunds")
    assert status.status_code == 200
    assert status.json()["line_balances"] == [
        {
            "external_line_id": "line-1",
            "title": "Storefront chair",
            "sku": "STOREFRONT-CHAIR-748",
            "original_quantity": 1,
            "remaining_quantity": 1,
            "original_amount_minor": 115000,
            "remaining_amount_minor": 57500,
        }
    ]

    command_headers = {**refund_ops_headers, "Host": "test"}
    commands = await owner_client.get(
        "/api/v1/ops-commerce/v1/refund-commands", headers=command_headers
    )
    assert commands.status_code == 200
    command = next(row for row in commands.json()["items"] if row["request_id"] == request_id)
    assert command["handoff_id"] == str(handoff.id)
    assert command["external_order_id"] == payload["external_order_id"]
    assert command["original_transaction_id"] == "gateway-ref-748-001"
    assert command["amount_minor"] == 57500

    dispatching = await owner_client.post(
        f"/api/v1/ops-commerce/v1/refund-commands/{request_id}/outcome",
        json={"status": "dispatching"},
        headers=command_headers,
    )
    assert dispatching.status_code == 200
    assert dispatching.json()["status"] == "dispatching"

    event = _provider_event(
        provider_refund_id="refund-partial-754",
        capture_id="gateway-ref-748-001",
        amount_minor=57500,
        request_id=request_id,
    )
    accepted = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events", json=event, headers=command_headers
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "succeeded"
    assert accepted.json()["provider_outcome"] == "succeeded"
    assert accepted.json()["request_id"] == request_id
    assert accepted.json()["external_order_id"] == payload["external_order_id"]

    duplicate = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events", json=event, headers=command_headers
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    order = await async_db.get(SalesOrder, handoff.sales_order_id)
    assert order is not None
    await async_db.refresh(order)
    assert str(order.amount_paid) == "575.00"
    refund = await async_db.get(OpsCommerceRefund, UUID(request_id))
    assert refund is not None
    assert refund.provider_amount_minor == 57500
    assert refund.financial_journal_id is not None
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(
                JournalEntry.document_id == refund.id,
                JournalEntry.source == "storefront_refund",
            )
        )
        == 1
    )

    conflicting = _provider_event(
        provider_refund_id="refund-partial-754",
        capture_id="gateway-ref-748-001",
        amount_minor=58000,
        request_id=request_id,
        canonical="same-provider-id-conflicting-amount",
    )
    conflict_response = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=conflicting,
        headers=command_headers,
    )
    assert conflict_response.status_code == 200
    assert conflict_response.json()["status"] == "needs_review"
    assert conflict_response.json()["request_id"] is None
    await async_db.refresh(refund)
    assert refund.provider_amount_minor == 57500
    assert refund.provider_outcome == "succeeded"
    assert await async_db.scalar(select(func.count()).select_from(OpsCommerceRefundEvent)) == 2


@pytest.mark.asyncio
async def test_out_of_band_success_does_not_claim_an_unbound_staff_intent(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    _, handoff = await _import_uninvoiced_handoff(owner_client, async_db, refund_ops_headers)
    await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    requested = await async_client.post(
        f"/api/v1/storefront/orders/{handoff.id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 50000},
    )
    assert requested.status_code == 200
    local_request_id = UUID(requested.json()["id"])

    event = _provider_event(
        provider_refund_id="refund-out-of-band-754",
        capture_id="gateway-ref-748-001",
        amount_minor=50000,
    )
    recorded = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events", json=event, headers=refund_ops_headers
    )
    assert recorded.status_code == 200
    assert recorded.json()["status"] == "needs_review"
    assert recorded.json()["provider_outcome"] == "succeeded"
    assert recorded.json()["request_id"] != str(local_request_id)
    assert recorded.json()["external_order_id"] == handoff.external_order_id

    local_request = await async_db.get(OpsCommerceRefund, local_request_id)
    assert local_request is not None
    assert local_request.request_origin == "staff"
    assert local_request.provider_refund_id is None
    assert local_request.requested_by_user_id is not None
    provider_record = await async_db.get(OpsCommerceRefund, UUID(recorded.json()["request_id"]))
    assert provider_record is not None
    assert provider_record.request_origin == "provider"
    assert provider_record.requested_by_user_id is None
    assert provider_record.status == "needs_review"
    assert provider_record.financial_journal_id is not None
    order = await async_db.get(SalesOrder, handoff.sales_order_id)
    assert order is not None
    await async_db.refresh(order)
    assert str(order.amount_paid) == "650.00"


@pytest.mark.asyncio
async def test_invoiced_refund_is_bounded_by_completed_return_credit_note(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    payload, handoff, sku_id = await _import_stocked_handoff(
        owner_client, async_db, refund_ops_headers
    )
    order = await async_db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(SalesOrder.id == handoff.sales_order_id)
    )
    assert order is not None and order.invoice_id is not None
    handoff_id = handoff.id
    invoice_id = order.invoice_id
    location_id = order.location_id
    assert str(order.amount_paid) == "1150.00"
    invoice = await TaxInvoiceCRUD(async_db).get_by_id(invoice_id)
    assert invoice is not None and len(invoice.lines) == 1
    invoice_line = invoice.lines[0]
    invoice_line_id = invoice_line.id
    assert location_id is not None

    other_team = Team(name=f"Refund scope fixture {uuid4()}")
    async_db.add(other_team)
    await async_db.flush()
    foreign_email = f"refund-scope-{uuid4()}@example.com"
    async_db.add(
        User(
            team_id=other_team.id,
            email=foreign_email,
            password_hash=hash_password("refund-scope-password"),
            role="books",
        )
    )
    await async_db.flush()
    owner_client.cookies.clear()
    foreign_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": foreign_email, "password": "refund-scope-password"},
    )
    assert foreign_login.status_code == 200
    foreign_scope = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 1000},
    )
    assert foreign_scope.status_code == 404

    owner_client.cookies.clear()
    till_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": "till@example.com", "password": settings.seed_till_password},
    )
    assert till_login.status_code == 200
    unauthorized = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 1000},
    )
    assert unauthorized.status_code == 403

    owner_client.cookies.clear()
    books_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert books_login.status_code == 200
    before_return = await owner_client.get(f"/api/v1/storefront/orders/{handoff_id}/refunds")
    assert before_return.status_code == 200
    assert before_return.json()["invoice_refund_eligible"] is False
    missing_return = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 1000},
    )
    assert missing_return.status_code == 409

    stock_query = select(LocationStock.on_hand).where(
        LocationStock.sku_id == UUID(sku_id),
        LocationStock.location_id == location_id,
    )
    before_return_qty = await async_db.scalar(stock_query)
    assert before_return_qty == 1
    owner_client.cookies.clear()
    owner_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": settings.seed_owner_password},
    )
    assert owner_login.status_code == 200
    created_return = await owner_client.post(
        "/api/v1/returns",
        json={
            "invoice_id": str(invoice_id),
            "location_id": str(location_id),
            "reason": "unwanted",
            "disposition": StockReturnDisposition.RESTOCK.value,
            "lines": [{"invoice_line_id": str(invoice_line_id), "qty": 1}],
        },
    )
    assert created_return.status_code == 201
    completed_return = await owner_client.post(
        f"/api/v1/returns/{created_return.json()['id']}/complete"
    )
    assert completed_return.status_code == 200
    assert completed_return.json()["status"] == StockReturnStatus.COMPLETED.value
    credit_note_id = UUID(completed_return.json()["credit_note_id"])
    credit_note = await async_db.get(CreditNote, credit_note_id)
    assert credit_note is not None and str(credit_note.total_inc_vat) == "1150.00"
    after_return_qty = await async_db.scalar(stock_query)
    assert after_return_qty == 2
    duplicate_complete = await owner_client.post(
        f"/api/v1/returns/{created_return.json()['id']}/complete"
    )
    assert duplicate_complete.status_code == 409
    assert await async_db.scalar(stock_query) == after_return_qty
    second_return = await owner_client.post(
        "/api/v1/returns",
        json={
            "invoice_id": str(invoice_id),
            "location_id": str(location_id),
            "reason": "unwanted",
            "disposition": StockReturnDisposition.RESTOCK.value,
            "lines": [{"invoice_line_id": str(invoice_line_id), "qty": 1}],
        },
    )
    assert second_return.status_code == 409

    selected_lines = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={
            "idempotency_key": str(uuid4()),
            "selected_lines": [{"external_line_id": "line-1", "quantity": 1}],
        },
    )
    assert selected_lines.status_code == 409
    cancel_request = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={
            "idempotency_key": str(uuid4()),
            "amount_minor": 115000,
            "cancel_order": True,
        },
    )
    assert cancel_request.status_code == 409
    over_credit = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 115001},
    )
    assert over_credit.status_code == 400

    first_request = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 60000},
    )
    assert first_request.status_code == 200
    first_refund_id = first_request.json()["id"]
    first_event = _provider_event(
        provider_refund_id="refund-invoice-partial-754-a",
        capture_id="gateway-ref-748-001",
        amount_minor=60000,
        request_id=first_refund_id,
    )
    first_accepted = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=first_event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert first_accepted.status_code == 200
    assert first_accepted.json()["status"] == "succeeded"
    assert first_accepted.json()["provider_outcome"] == "succeeded"
    assert first_accepted.json()["resolution_code"] is None

    mismatched_event = _provider_event(
        provider_refund_id="refund-invoice-partial-754-a",
        capture_id="different-capture-reference",
        amount_minor=60000,
        request_id=first_refund_id,
        canonical="linkage-mismatch-after-first-invoice-refund",
    )
    mismatched_event["outcome"] = "failed"
    mismatch_response = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=mismatched_event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert mismatch_response.status_code == 200
    assert mismatch_response.json()["status"] == "needs_review"
    assert mismatch_response.json()["resolution_code"] == "binding_capture_mismatch"
    assert mismatch_response.json()["request_id"] is None
    first_refund = await async_db.get(OpsCommerceRefund, UUID(first_refund_id))
    assert first_refund is not None
    assert first_refund.provider_refund_id == "refund-invoice-partial-754-a"
    assert first_refund.provider_amount_minor == 60000
    assert first_refund.provider_outcome == "succeeded"
    assert first_refund.status == "succeeded"

    second_request = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 55000},
    )
    assert second_request.status_code == 200
    exhausted = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff_id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 1},
    )
    assert exhausted.status_code == 400

    second_refund_id = second_request.json()["id"]
    second_event = _provider_event(
        provider_refund_id="refund-invoice-partial-754-b",
        capture_id="gateway-ref-748-001",
        amount_minor=55000,
        request_id=second_refund_id,
    )
    second_accepted = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=second_event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert second_accepted.status_code == 200
    assert second_accepted.json()["status"] == "succeeded"
    duplicate_event = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=second_event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert duplicate_event.status_code == 200
    assert duplicate_event.json()["duplicate"] is True

    await async_db.refresh(order)
    assert order.status.value == "invoiced"
    assert str(order.amount_paid) == "0.00"
    await async_db.refresh(handoff)
    assert handoff.cancelled_at is None
    assert handoff.captured_amount_minor == 115000
    assert handoff.payload["totals"]["total_minor_zar"] == 115000
    assert await async_db.scalar(stock_query) == after_return_qty
    status = await owner_client.get(f"/api/v1/storefront/orders/{handoff_id}/refunds")
    assert status.status_code == 200
    assert status.json()["confirmed_refund_minor"] == 115000
    assert status.json()["available_refund_minor"] == 0

    for refund_id, amount in ((first_refund_id, "600.00"), (second_refund_id, "550.00")):
        refund = await async_db.get(OpsCommerceRefund, UUID(refund_id))
        assert refund is not None and refund.financial_journal_id is not None
        journal_lines = list(
            (
                await async_db.execute(
                    select(Account.code, JournalLine.debit_zar, JournalLine.credit_zar)
                    .join(JournalLine, JournalLine.account_id == Account.id)
                    .where(JournalLine.entry_id == refund.financial_journal_id)
                )
            ).all()
        )
        assert sorted((code, str(debit), str(credit)) for code, debit, credit in journal_lines) == [
            ("1150", "0.00", amount),
            ("1200", amount, "0.00"),
        ]
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(
                JournalEntry.source == "storefront_refund",
                JournalEntry.document_id.in_([UUID(first_refund_id), UUID(second_refund_id)]),
            )
        )
        == 2
    )


@pytest.mark.asyncio
async def test_post_invoice_provider_success_without_accepted_return_is_observed_for_review(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    _, handoff, _ = await _import_stocked_handoff(owner_client, async_db, refund_ops_headers)
    order = await async_db.get(SalesOrder, handoff.sales_order_id)
    assert order is not None and order.invoice_id is not None
    original_paid = order.amount_paid

    event = _provider_event(
        provider_refund_id="refund-invoice-no-return-754",
        capture_id="gateway-ref-748-001",
        amount_minor=25000,
    )
    recorded = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert recorded.status_code == 200
    assert recorded.json()["status"] == "needs_review"
    assert recorded.json()["provider_outcome"] == "succeeded"
    assert recorded.json()["resolution_code"] is None
    assert recorded.json()["request_id"] is not None

    provider_refund = await async_db.get(OpsCommerceRefund, UUID(recorded.json()["request_id"]))
    assert provider_refund is not None
    assert provider_refund.request_origin == "provider"
    assert provider_refund.provider_outcome == "succeeded"
    assert provider_refund.status == "needs_review"
    assert provider_refund.failure_code == "invoice_requires_accepted_return_reconciliation"
    assert provider_refund.financial_journal_id is None
    await async_db.refresh(order)
    assert order.amount_paid == original_paid - 250
    assert (
        await async_db.scalar(
            select(CreditNote.id).where(CreditNote.invoice_id == order.invoice_id)
        )
        is None
    )
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(
                JournalEntry.document_id == provider_refund.id,
                JournalEntry.source == "storefront_refund",
            )
        )
        == 0
    )
    await async_db.refresh(handoff)
    assert handoff.captured_amount_minor == 115000
    assert handoff.payload["totals"]["total_minor_zar"] == 115000


@pytest.mark.asyncio
async def test_unmatched_signed_refund_event_reports_binding_resolution_code(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    event = _provider_event(
        provider_refund_id="refund-unmatched-capture-754",
        capture_id="unknown-capture-reference",
        amount_minor=10000,
    )
    response = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "needs_review"
    assert response.json()["resolution_code"] == "binding_capture_not_uniquely_matched"
    assert response.json()["request_id"] is None
    assert response.json()["handoff_id"] is None
    observation = await async_db.scalar(
        select(OpsCommerceRefundEvent).where(
            OpsCommerceRefundEvent.provider_refund_id == "refund-unmatched-capture-754"
        )
    )
    assert observation is not None
    assert observation.signature_verified is True
    assert observation.resolution_code == "binding_capture_not_uniquely_matched"


@pytest.mark.asyncio
async def test_cancelled_order_keeps_refund_history_readable_and_late_event_does_not_release_twice(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    _, handoff, stocked_sku_id = await _import_mixed_uninvoiced_handoff(
        owner_client, async_db, refund_ops_headers
    )
    order = await async_db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(SalesOrder.id == handoff.sales_order_id)
    )
    assert order is not None and order.invoice_id is None
    assert order.location_id is not None
    line = next(line for line in order.lines if str(line.sku_id) == stocked_sku_id)
    stock_query = select(LocationStock.on_hand).where(
        LocationStock.sku_id == line.sku_id,
        LocationStock.location_id == order.location_id,
    )
    before_cancel = await async_db.scalar(stock_query)
    assert before_cancel == 1

    request = await owner_client.post(
        f"/api/v1/storefront/orders/{handoff.id}/refunds",
        json={
            "idempotency_key": str(uuid4()),
            "amount_minor": 230000,
            "cancel_order": True,
        },
    )
    assert request.status_code == 200
    event = _provider_event(
        provider_refund_id="refund-cancel-order-754",
        capture_id="gateway-ref-748-001",
        amount_minor=230000,
        request_id=request.json()["id"],
    )
    completed = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "succeeded"
    after_cancel = await async_db.scalar(stock_query)
    assert after_cancel == before_cancel + 1
    await async_db.refresh(order)
    await async_db.refresh(handoff)
    assert order.status.value == "cancelled"
    assert order.amount_paid == 0
    assert handoff.cancelled_at is not None
    assert handoff.fulfillment_status == "cancelled"
    assert handoff.fulfillment_revision == 1

    status = await owner_client.get(f"/api/v1/storefront/orders/{handoff.id}/refunds")
    assert status.status_code == 200
    assert status.json()["confirmed_refund_minor"] == 230000
    assert status.json()["available_refund_minor"] == 0
    assert len(status.json()["items"]) == 1

    late_event = _provider_event(
        provider_refund_id="refund-cancel-order-754",
        capture_id="gateway-ref-748-001",
        amount_minor=230000,
        request_id=request.json()["id"],
        canonical="late-webhook-same-refund-754",
    )
    late_event["event_source"] = "webhook"
    late_event["webhook_id"] = "peach-refund-webhook-late-754"
    late = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=late_event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert late.status_code == 200
    assert late.json()["status"] == "succeeded"
    assert late.json()["resolution_code"] is None
    assert await async_db.scalar(stock_query) == after_cancel
    await async_db.refresh(handoff)
    assert handoff.fulfillment_revision == 1
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(OpsCommerceRefundEvent)
            .where(OpsCommerceRefundEvent.refund_id == UUID(request.json()["id"]))
        )
        == 2
    )

    out_of_band_event = _provider_event(
        provider_refund_id="refund-after-cancel-out-of-band-754",
        capture_id="gateway-ref-748-001",
        amount_minor=1000,
    )
    out_of_band = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=out_of_band_event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert out_of_band.status_code == 200
    assert out_of_band.json()["status"] == "needs_review"
    assert out_of_band.json()["provider_outcome"] == "succeeded"
    assert out_of_band.json()["resolution_code"] is None
    assert out_of_band.json()["request_id"] is not None
    assert await async_db.scalar(stock_query) == after_cancel
    await async_db.refresh(handoff)
    assert handoff.fulfillment_revision == 1
    after_out_of_band = await owner_client.get(f"/api/v1/storefront/orders/{handoff.id}/refunds")
    assert after_out_of_band.status_code == 200
    assert after_out_of_band.json()["available_refund_minor"] == 0
    assert len(after_out_of_band.json()["items"]) == 2


@pytest.mark.asyncio
async def test_refund_command_feed_does_not_starve_new_work_with_old_unknown_rows(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    _, handoff = await _import_uninvoiced_handoff(owner_client, async_db, refund_ops_headers)
    order = await async_db.get(SalesOrder, handoff.sales_order_id)
    assert order is not None
    company_id = UUID(refund_ops_headers["X-Ops-Company-ID"])
    oldest = datetime.utcnow() - timedelta(days=1)
    async_db.add_all(
        [
            OpsCommerceRefund(
                company_id=company_id,
                handoff_id=handoff.id,
                sales_order_id=order.id,
                requested_by_user_id=None,
                request_origin="staff",
                idempotency_key=f"unresolved-{uuid4()}",
                amount_minor=1,
                currency_code="ZAR",
                allocation={},
                selected_lines={},
                cancel_order=False,
                status="unknown" if index % 2 else "pending",
                signature_verified=False,
                created_at=oldest + timedelta(seconds=index),
            )
            for index in range(105)
        ]
    )
    await async_db.flush()

    async_client.cookies.clear()
    books_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert books_login.status_code == 200
    request = await async_client.post(
        f"/api/v1/storefront/orders/{handoff.id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 1000},
    )
    assert request.status_code == 200

    feed = await owner_client.get(
        "/api/v1/ops-commerce/v1/refund-commands?limit=100",
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert feed.status_code == 200
    assert [item["request_id"] for item in feed.json()["items"]] == [request.json()["id"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_outcome", ["failed", "succeeded"])
async def test_unresolved_preinvoice_refund_blocks_invoice_until_terminal_provider_outcome(
    provider_outcome: str,
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    refund_ops_headers: dict[str, str],
) -> None:
    _, handoff = await _import_uninvoiced_handoff(owner_client, async_db, refund_ops_headers)
    sales_order_id = handoff.sales_order_id
    order = await async_db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(SalesOrder.id == sales_order_id)
    )
    assert order is not None and len(order.lines) == 1
    invoice_location_id = await async_db.scalar(
        select(Location.id).where(Location.name == "Kramerville")
    )
    assert invoice_location_id is not None
    stock = await async_db.scalar(
        select(LocationStock).where(
            LocationStock.sku_id == order.lines[0].sku_id,
            LocationStock.location_id == invoice_location_id,
        )
    )
    assert stock is not None and stock.on_hand > 0
    order.location_id = invoice_location_id
    await async_db.flush()
    async_client.cookies.clear()
    books_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert books_login.status_code == 200
    request = await async_client.post(
        f"/api/v1/storefront/orders/{handoff.id}/refunds",
        json={"idempotency_key": str(uuid4()), "amount_minor": 50000},
    )
    assert request.status_code == 200

    async_client.cookies.clear()
    owner_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": settings.seed_owner_email, "password": settings.seed_owner_password},
    )
    assert owner_login.status_code == 200
    blocked_invoice = await async_client.post(f"/api/v1/orders/{sales_order_id}/invoice")
    assert blocked_invoice.status_code == 409

    event = _provider_event(
        provider_refund_id=f"refund-before-invoice-{provider_outcome}-754",
        capture_id="gateway-ref-748-001",
        amount_minor=50000,
        request_id=request.json()["id"],
    )
    event["outcome"] = provider_outcome
    resolved = await owner_client.post(
        "/api/v1/ops-commerce/v1/refund-events",
        json=event,
        headers={**refund_ops_headers, "Host": "test"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == provider_outcome

    invoice = await owner_client.post(f"/api/v1/orders/{sales_order_id}/invoice")
    assert invoice.status_code == 200, invoice.text
    assert invoice.json()["status"] == "invoiced"
    assert invoice.json()["amount_paid"] == (
        "650.00" if provider_outcome == "succeeded" else "1150.00"
    )
    refund = await async_db.get(OpsCommerceRefund, UUID(request.json()["id"]))
    assert refund is not None and refund.status == provider_outcome
    if provider_outcome == "succeeded":
        assert refund.financial_journal_id is not None
    else:
        assert refund.financial_journal_id is None


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_parallel_refund_requests_reserve_capture_balance_once(
    postgres_container,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = make_url(async_url(postgres_container))
    database_name = f"refund_race_{uuid4().hex[:12]}"
    admin = await asyncpg.connect(
        user=base_url.username,
        password=base_url.password,
        host=base_url.host,
        port=base_url.port,
        database=base_url.database,
    )
    await admin.execute(f'CREATE DATABASE "{database_name}"')
    race_engine = create_async_engine(
        base_url.set(database=database_name).render_as_string(hide_password=False),
        pool_size=5,
    )
    try:
        async with race_engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
            await connection.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(race_engine, expire_on_commit=False, class_=AsyncSession)
        async with maker() as session:
            await RoleSeedService(session).seed()
            await BootstrapService(session).seed_if_empty()
            await LocationSeedService(session).seed_if_empty()
            await RoleUserSeedService(session).seed()
            await StorefrontSystemActorService(session).ensure()
            coa = ChartOfAccountsSeedService(session)
            await coa.seed_if_empty()
            await coa.ensure_opening_equity()
            await coa.ensure_customer_deposits()
            await coa.ensure_storefront_gateway_clearing()
            await coa.ensure_category_chart()
            await coa.ensure_bank_accounts()
            await TillSeedService(session).seed_if_empty()
            await session.commit()
            company_id = await session.scalar(select(Team.id))
            assert company_id is not None

        monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id), raising=False)
        monkeypatch.setattr(
            settings, "ops_commerce_token", "storefront-refund-race-token", raising=False
        )
        monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test", raising=False)
        ops_headers = {
            "Authorization": "Bearer storefront-refund-race-token",
            "X-Ops-Company-ID": str(company_id),
        }

        async def independent_db_session():
            async with maker() as session:
                yield session

        previous_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = independent_db_session
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as setup_client:
                login = await setup_client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": settings.seed_owner_email,
                        "password": settings.seed_owner_password,
                    },
                )
                assert login.status_code == 200
                fixture_tag = uuid4().hex[:10]
                payload, sku_id = await _paid_order_payload(setup_client, fixture_tag=fixture_tag)
                now = datetime.now(timezone.utc)
                offer = await setup_client.patch(
                    f"/api/v1/skus/{sku_id}",
                    json={
                        "made_to_order_capacity": 3,
                        "made_to_order_lead_time_min_days": 28,
                        "made_to_order_lead_time_max_days": 42,
                        "made_to_order_expires_at": (now + timedelta(days=7)).isoformat(),
                    },
                )
                assert offer.status_code == 200
                estimated_from = (now + timedelta(days=28)).date().isoformat()
                estimated_by = (now + timedelta(days=42)).date().isoformat()
                line = payload["lines"][0]
                line["fulfillment_promise"] = {
                    "kind": "made_to_order",
                    "offer_id": offer.json()["made_to_order_offer_id"],
                    "min_lead_time_days": 28,
                    "max_lead_time_days": 42,
                    "estimated_from": estimated_from,
                    "estimated_by": estimated_by,
                    "expires_at": offer.json()["made_to_order_expires_at"],
                }
                payload["fulfillment_promise"] = {
                    "version": 1,
                    "kind": "made_to_order",
                    "accepted_at": now.isoformat(),
                    "estimated_from": estimated_from,
                    "estimated_by": estimated_by,
                }
                payload["company_id"] = str(company_id)
                imported = await setup_client.post(
                    "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
                )
                assert imported.status_code == 201
                handoff_id = imported.json()["id"]

            async def request_refund(idempotency_key: str):
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    login_response = await client.post(
                        "/api/v1/auth/login",
                        json={
                            "email": "books@example.com",
                            "password": settings.seed_books_password,
                        },
                    )
                    assert login_response.status_code == 200
                    return await client.post(
                        f"/api/v1/storefront/orders/{handoff_id}/refunds",
                        json={"idempotency_key": idempotency_key, "amount_minor": 65000},
                    )

            responses = await asyncio.gather(
                request_refund(str(uuid4())),
                request_refund(str(uuid4())),
            )
            assert sorted(response.status_code for response in responses) == [200, 400], [
                (response.status_code, response.text) for response in responses
            ]
            accepted = next(response for response in responses if response.status_code == 200)
            assert accepted.json()["amount_minor"] == 65000

            async with AsyncClient(transport=transport, base_url="http://test") as status_client:
                login_response = await status_client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "books@example.com",
                        "password": settings.seed_books_password,
                    },
                )
                assert login_response.status_code == 200
                status = await status_client.get(f"/api/v1/storefront/orders/{handoff_id}/refunds")
            assert status.status_code == 200
            assert status.json()["reserved_refund_minor"] == 65000
            assert status.json()["available_refund_minor"] == 50000
            assert len(status.json()["items"]) == 1
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_override
    finally:
        await race_engine.dispose()
        await admin.execute(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        await admin.close()
