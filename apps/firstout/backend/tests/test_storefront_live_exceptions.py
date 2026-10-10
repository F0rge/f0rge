"""Real commerce conditions require worker convergence, never operator flags."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.storefront_commerce_exception import StorefrontCommerceException
from app.models.team import Team


@pytest_asyncio.fixture
async def machine_headers(
    monkeypatch: pytest.MonkeyPatch, async_db: AsyncSession
) -> dict[str, str]:
    company = await async_db.scalar(select(Team.id))
    assert company is not None
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company))
    monkeypatch.setattr(settings, "ops_commerce_token", "live-exception-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    return {"Authorization": "Bearer live-exception-token", "X-Ops-Company-ID": str(company)}


def _scan(*, present: bool, observed_at: datetime | None = None) -> dict[str, object]:
    now = observed_at or datetime.now(timezone.utc)
    return {
        "observed_at": now.isoformat(),
        "observations": [
            {
                "correlation_id": "storefront:stale_sync:catalogue",
                "kind": "stale_sync",
                "status": "aged",
                "explanation": "The live catalogue projection is stale",
                "safe_action": "refresh_projection",
                "last_error": "projection_stale",
                "provider_verified": False,
                "blocks_checkout": True,
                "detected_at": (now - timedelta(minutes=10)).isoformat(),
            }
        ]
        if present
        else [],
    }


@pytest.mark.asyncio
async def test_live_condition_requires_queued_repair_and_fresh_complete_scan(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    machine_headers: dict[str, str],
) -> None:
    scan_path = "/api/v1/ops-commerce/v1/exceptions/observations"
    command_path = "/api/v1/ops-commerce/v1/exceptions/commands"
    first_scan = _scan(present=True)
    posted = await owner_client.post(scan_path, json=first_scan, headers=machine_headers)
    assert posted.status_code == 200, posted.text
    duplicate = await owner_client.post(scan_path, json=first_scan, headers=machine_headers)
    assert duplicate.status_code == 200
    listed = await owner_client.get("/api/v1/storefront/exceptions")
    row = listed.json()["items"][0]
    assert row["status"] == "aged" and row["blocks_checkout"] is True
    assert listed.json()["checkout_allowed"] is False
    assert await async_db.scalar(select(func.count()).select_from(StorefrontCommerceException)) == 1
    delayed_empty_scan = _scan(present=False)
    repair = {
        "reason": "Refresh the actual catalogue projection",
        "idempotency_key": "live-repair-1",
    }
    queued = await owner_client.post(
        f"/api/v1/storefront/exceptions/{row['id']}/repair", json=repair
    )
    assert queued.status_code == 200
    assert queued.json()["status"] == "aged" and queued.json()["repair_count"] == 0
    assert queued.json()["blocks_checkout"] is True
    assert queued.json()["audits"][-1]["outcome"] == "repair_requested"
    replay = await owner_client.post(
        f"/api/v1/storefront/exceptions/{row['id']}/repair", json=repair
    )
    assert replay.status_code == 200
    another_request = await owner_client.post(
        f"/api/v1/storefront/exceptions/{row['id']}/repair",
        json={**repair, "idempotency_key": "live-also-queued"},
    )
    assert another_request.status_code == 200
    feed = await owner_client.get(command_path, headers=machine_headers)
    assert feed.status_code == 200
    commands = feed.json()["items"]
    assert len(commands) == 1 and commands[0]["action"] == "refresh_projection"
    result_path = f"{command_path}/{commands[0]['id']}/result"
    # A scan begun before the command but received afterward cannot attest its effect.
    delayed = await owner_client.post(scan_path, json=delayed_empty_scan, headers=machine_headers)
    assert delayed.status_code == 200
    fabricated = await owner_client.post(
        result_path,
        json={"outcome": "repaired", "detail": "projection_refreshed"},
        headers=machine_headers,
    )
    assert fabricated.status_code == 409
    resumed = await owner_client.post(scan_path, json=_scan(present=True), headers=machine_headers)
    assert resumed.status_code == 200
    failed = await owner_client.post(
        result_path,
        json={"outcome": "not_repaired", "detail": "ops_unavailable"},
        headers=machine_headers,
    )
    assert failed.status_code == 200
    still_open = await owner_client.get(f"/api/v1/storefront/exceptions/{row['id']}")
    assert still_open.json()["status"] == "aged" and still_open.json()["blocks_checkout"]
    assert still_open.json()["audits"][-1]["outcome"] == "repair_failed"
    retry = await owner_client.post(
        f"/api/v1/storefront/exceptions/{row['id']}/repair",
        json={**repair, "idempotency_key": "live-repair-2"},
    )
    assert retry.status_code == 200
    retry_feed = await owner_client.get(command_path, headers=machine_headers)
    second = retry_feed.json()["items"]
    assert len(second) == 1 and second[0]["id"] != commands[0]["id"]
    cleared = await owner_client.post(scan_path, json=_scan(present=False), headers=machine_headers)
    assert cleared.status_code == 200
    repaired_path = f"{command_path}/{second[0]['id']}/result"
    completion = {"outcome": "repaired", "detail": "projection_refreshed"}
    applied = await owner_client.post(repaired_path, json=completion, headers=machine_headers)
    assert applied.status_code == 200
    repeated = await owner_client.post(repaired_path, json=completion, headers=machine_headers)
    assert repeated.status_code == 200
    resolved = await owner_client.get(f"/api/v1/storefront/exceptions/{row['id']}")
    assert resolved.json()["status"] == "resolved" and resolved.json()["repair_count"] == 1
    assert resolved.json()["blocks_checkout"] is False
    # An old in-flight scan cannot reopen or clear a newer source condition.
    old = await owner_client.post(scan_path, json=first_scan, headers=machine_headers)
    assert old.status_code == 200
    persisted = await async_db.get(StorefrontCommerceException, UUID(row["id"]))
    assert persisted is not None and persisted.status == "resolved"
    safety = await owner_client.get(
        "/api/v1/ops-commerce/v1/checkout-safety", headers=machine_headers
    )
    assert safety.json()["checkout_allowed"] is True
    denied = await owner_client.post(scan_path, json=_scan(present=True))
    assert denied.status_code == 401
    wrong_company = await owner_client.post(
        scan_path,
        json=_scan(present=True),
        headers={**machine_headers, "X-Ops-Company-ID": str(uuid4())},
    )
    assert wrong_company.status_code == 403
    future = await owner_client.post(
        scan_path,
        json=_scan(present=False, observed_at=datetime.now(timezone.utc) + timedelta(days=1)),
        headers=machine_headers,
    )
    assert future.status_code == 400


@pytest.mark.asyncio
async def test_failed_or_old_scans_cannot_clear_live_conditions_or_fixture_rows(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    machine_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "storefront_exception_fixtures", True)
    seeded = await owner_client.post("/api/v1/storefront/exceptions/seed")
    assert seeded.status_code == 200
    scan_path = "/api/v1/ops-commerce/v1/exceptions/observations"
    observed = await owner_client.post(scan_path, json=_scan(present=True), headers=machine_headers)
    assert observed.status_code == 200
    invalid = _scan(present=False, observed_at=datetime.now(timezone.utc) - timedelta(minutes=6))
    rejected = await owner_client.post(scan_path, json=invalid, headers=machine_headers)
    assert rejected.status_code == 400
    wrong_action = _scan(present=True)
    wrong_action["observations"][0]["safe_action"] = "force_capture"
    unsafe = await owner_client.post(scan_path, json=wrong_action, headers=machine_headers)
    assert unsafe.status_code == 422
    unknown_field = {**_scan(present=False), "provider_success": True}
    tampered = await owner_client.post(scan_path, json=unknown_field, headers=machine_headers)
    assert tampered.status_code == 422
    live = await async_db.scalar(
        select(StorefrontCommerceException).where(StorefrontCommerceException.source == "commerce")
    )
    assert live is not None and live.status == "aged" and live.blocks_checkout
    clear_live = await owner_client.post(
        scan_path, json=_scan(present=False), headers=machine_headers
    )
    assert clear_live.status_code == 200 and clear_live.json()["checkout_allowed"] is False
    fixtures = list(
        (
            await async_db.scalars(
                select(StorefrontCommerceException).where(
                    StorefrontCommerceException.source == "fixture"
                )
            )
        ).all()
    )
    assert len(fixtures) == 7 and all(row.status != "resolved" for row in fixtures)


@pytest.mark.asyncio
async def test_live_unknown_payment_queues_provider_read_under_financial_permission(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    machine_headers: dict[str, str],
) -> None:
    scan = _scan(present=True)
    scan["observations"][0].update(
        kind="unknown_payment",
        correlation_id="storefront:unknown_payment:attempt-1",
        status="open",
        safe_action="verify_with_provider",
        blocks_checkout=False,
        amount_minor=115000,
        payment_reference="capture-1",
        provider_verified=False,
    )
    posted = await owner_client.post(
        "/api/v1/ops-commerce/v1/exceptions/observations", json=scan, headers=machine_headers
    )
    assert posted.status_code == 200
    listed = await owner_client.get("/api/v1/storefront/exceptions")
    row = listed.json()["items"][0]
    async_client.cookies.clear()
    till = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till@example.com", "password": settings.seed_till_password},
    )
    assert till.status_code == 200
    redacted = await async_client.get("/api/v1/storefront/exceptions")
    assert redacted.json()["items"][0]["amount_minor"] is None
    body = {"reason": "Read the actual hosted payment status", "idempotency_key": "verify-source-1"}
    denied = await async_client.post(f"/api/v1/storefront/exceptions/{row['id']}/repair", json=body)
    assert denied.status_code == 403
    async_client.cookies.clear()
    books = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert books.status_code == 200
    queued = await async_client.post(f"/api/v1/storefront/exceptions/{row['id']}/repair", json=body)
    assert queued.status_code == 200
    assert queued.json()["status"] == "open" and not queued.json()["provider_verified"]
    assert queued.json()["repair_pending"] is True
    commands = await async_client.get(
        "/api/v1/ops-commerce/v1/exceptions/commands", headers=machine_headers
    )
    assert [command["action"] for command in commands.json()["items"]] == ["verify_with_provider"]


@pytest.mark.asyncio
async def test_live_scans_and_commands_are_isolated_by_authenticated_company(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    machine_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = "/api/v1/ops-commerce/v1/exceptions"
    first = await owner_client.post(
        f"{path}/observations", json=_scan(present=True), headers=machine_headers
    )
    assert first.status_code == 200
    row = (await owner_client.get("/api/v1/storefront/exceptions")).json()["items"][0]
    queued = await owner_client.post(
        f"/api/v1/storefront/exceptions/{row['id']}/repair",
        json={
            "reason": "Refresh this company's live projection",
            "idempotency_key": "company-repair-1",
        },
    )
    assert queued.status_code == 200
    feed = await owner_client.get(f"{path}/commands", headers=machine_headers)
    command_id = feed.json()["items"][0]["id"]
    from f0rge_db.crud import unit_of_work

    other = Team(name="Other exception company")
    async with unit_of_work(async_db):
        async_db.add(other)
        await async_db.flush()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(other.id))
    other_headers = {**machine_headers, "X-Ops-Company-ID": str(other.id)}
    empty = await owner_client.get(f"{path}/commands", headers=other_headers)
    assert empty.status_code == 200 and empty.json()["items"] == []
    unauthorized_result = await owner_client.post(
        f"{path}/commands/{command_id}/result",
        json={"outcome": "repaired", "detail": "projection_refreshed"},
        headers=other_headers,
    )
    assert unauthorized_result.status_code == 404
    scan = await owner_client.post(
        f"{path}/observations", json=_scan(present=False), headers=other_headers
    )
    assert scan.status_code == 200
    own = await async_db.get(StorefrontCommerceException, UUID(row["id"]))
    assert own is not None and own.status == "aged" and own.blocks_checkout
