"""Operator commerce exception queue, audited repair, and checkout safety."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.storefront_commerce_exception import (
    StorefrontCommerceException,
    StorefrontExceptionAlert,
    StorefrontExceptionAudit,
)
from app.models.team import Team


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


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


@pytest.fixture
def enable_exception_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storefront_exception_fixtures", True, raising=False)


@pytest.mark.asyncio
async def test_seeded_exceptions_repair_audit_denial_and_checkout_block(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    enable_exception_fixtures: None,
    ops_headers: dict[str, str],
) -> None:
    seeded = await owner_client.post("/api/v1/storefront/exceptions/seed")
    assert seeded.status_code == 200
    payload = seeded.json()
    kinds = {item["kind"] for item in payload["items"]}
    assert kinds == {
        "aged_hold",
        "stale_sync",
        "missing_operational_paid_order",
        "unknown_payment",
        "refund_mismatch",
        "fulfilment_drift",
        "capacity_conflict",
    }
    assert payload["checkout_allowed"] is False
    assert payload["paid_recovery_retained"] is True
    for item in payload["items"]:
        assert item["correlation_id"]
        assert item["age_seconds"] >= 0
        assert item["explanation"]
        assert item["safe_action"]
        assert item["status"] in {"open", "aged", "terminal", "resolved"}

    again = await owner_client.post("/api/v1/storefront/exceptions/seed")
    assert again.status_code == 200
    assert await async_db.scalar(select(func.count()).select_from(StorefrontCommerceException)) == 7

    by_kind = {item["kind"]: item for item in payload["items"]}
    stale = by_kind["stale_sync"]
    missing = by_kind["missing_operational_paid_order"]
    unknown = by_kind["unknown_payment"]
    refund = by_kind["refund_mismatch"]
    capacity = by_kind["capacity_conflict"]
    assert stale["status"] == "aged"
    assert capacity["status"] == "terminal"
    assert unknown["amount_minor"] == 115000
    assert refund["payment_reference"] == "seed-refund-mismatch"

    safety = await owner_client.get("/api/v1/ops-commerce/v1/checkout-safety", headers=ops_headers)
    assert safety.status_code == 200
    assert safety.json()["checkout_allowed"] is False
    assert safety.json()["paid_recovery_retained"] is True

    first = await owner_client.post(
        f"/api/v1/storefront/exceptions/{missing['id']}/repair",
        json={"reason": "Replay missing paid handoff", "idempotency_key": "repair-missing-1"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "resolved"
    assert first.json()["repair_count"] == 1
    replay = await owner_client.post(
        f"/api/v1/storefront/exceptions/{missing['id']}/repair",
        json={"reason": "Replay missing paid handoff", "idempotency_key": "repair-missing-1"},
    )
    assert replay.status_code == 200
    assert replay.json()["repair_count"] == 1
    second_key = await owner_client.post(
        f"/api/v1/storefront/exceptions/{missing['id']}/repair",
        json={
            "reason": "Second operator retry of same missing handoff",
            "idempotency_key": "repair-missing-2",
        },
    )
    assert second_key.status_code == 200
    assert second_key.json()["repair_count"] == 1
    audits = [row for row in second_key.json()["audits"] if row["outcome"] == "already_resolved"]
    assert len(audits) == 1
    assert audits[0]["reason"]
    assert audits[0]["actor_user_id"]

    stock = await owner_client.post(
        f"/api/v1/storefront/exceptions/{stale['id']}/repair",
        json={
            "reason": "Refresh stale operational projection",
            "idempotency_key": "repair-stale-1",
        },
    )
    assert stock.status_code == 200
    refund_ok = await owner_client.post(
        f"/api/v1/storefront/exceptions/{refund['id']}/repair",
        json={
            "reason": "Reproject verified refund observation",
            "idempotency_key": "repair-refund-1",
        },
    )
    assert refund_ok.status_code == 200
    assert refund_ok.json()["repair_count"] == 1
    refund_again = await owner_client.post(
        f"/api/v1/storefront/exceptions/{refund['id']}/repair",
        json={
            "reason": "Reproject verified refund observation",
            "idempotency_key": "repair-refund-1",
        },
    )
    assert refund_again.json()["repair_count"] == 1

    blocked = await owner_client.post(
        f"/api/v1/storefront/exceptions/{unknown['id']}/repair",
        json={"reason": "Mark unknown payment captured", "idempotency_key": "repair-unknown-1"},
    )
    assert blocked.status_code == 400
    assert "provider verification" in blocked.json()["detail"].lower()
    unknown_row = await async_db.get(StorefrontCommerceException, UUID(unknown["id"]))
    assert unknown_row is not None and unknown_row.status != "resolved"

    alert = await owner_client.post(
        "/api/v1/storefront/exceptions/alerts/test",
        json={"exception_id": missing["id"]},
    )
    assert alert.status_code == 200
    context = alert.json()["context"]
    assert alert.json()["queue_class"] == "aged"
    assert context["correlation_id"] == missing["correlation_id"]
    assert "payer@example.test" not in str(context)
    assert "seed-pay-unknown" not in str(context)
    inbox = await owner_client.get("/api/v1/storefront/exceptions/alerts")
    assert inbox.status_code == 200
    assert len(inbox.json()["items"]) == 1

    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    denied_list = await async_client.get("/api/v1/storefront/exceptions")
    assert denied_list.status_code == 403
    denied_repair = await async_client.post(
        f"/api/v1/storefront/exceptions/{stale['id']}/repair",
        json={"reason": "Warehouse should not repair", "idempotency_key": "wh-1"},
    )
    assert denied_repair.status_code == 403

    await _login(async_client, "till@example.com", settings.seed_till_password)
    till_list = await async_client.get("/api/v1/storefront/exceptions")
    assert till_list.status_code == 200
    till_unknown = next(
        item for item in till_list.json()["items"] if item["kind"] == "unknown_payment"
    )
    assert till_unknown["amount_minor"] is None
    assert till_unknown["payment_reference"] is None
    till_repair = await async_client.post(
        f"/api/v1/storefront/exceptions/{unknown['id']}/repair",
        json={"reason": "Till cannot repair financial rows", "idempotency_key": "till-unknown"},
    )
    assert till_repair.status_code == 403

    await _login(async_client, "books@example.com", settings.seed_books_password)
    books_list = await async_client.get("/api/v1/storefront/exceptions")
    books_unknown = next(
        item for item in books_list.json()["items"] if item["kind"] == "unknown_payment"
    )
    assert books_unknown["amount_minor"] == 115000
    books_missing = await async_client.post(
        f"/api/v1/storefront/exceptions/{missing['id']}/repair",
        json={
            "reason": "Books cannot retry operational handoff",
            "idempotency_key": "books-missing",
        },
    )
    assert books_missing.status_code == 403

    await _login(async_client, settings.seed_owner_email, settings.seed_owner_password)
    open_again = await owner_client.get(
        "/api/v1/ops-commerce/v1/checkout-safety", headers=ops_headers
    )
    assert open_again.json()["checkout_allowed"] is True
    assert await async_db.scalar(select(func.count()).select_from(StorefrontExceptionAudit)) >= 3
    assert await async_db.scalar(select(func.count()).select_from(StorefrontExceptionAlert)) == 1


@pytest.mark.asyncio
async def test_exception_fixtures_stay_off_by_default(owner_client: AsyncClient) -> None:
    resp = await owner_client.post("/api/v1/storefront/exceptions/seed")
    assert resp.status_code == 403
