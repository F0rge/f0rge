"""Restore rehearsal and paid-event replay on the existing exception queue."""

from __future__ import annotations

import datetime
from typing import Any, Optional

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.storefront_commerce_exception import StorefrontCommerceException
from app.models.team import Team
from app.services.storefront_recovery import (
    PROPOSED_BACKUP_POLICY,
    AuditView,
    RowView,
    assess_backup,
    gate_reason,
    measure_clocks,
    open_restore,
    reconcile_truth,
    replay_effect,
    resume_recovery,
    route_alert,
    state_from_rows,
    with_ops,
)

RESTORE_ID = "snap-20261002"
NOW = datetime.datetime(2026, 10, 3, 12, 0, 0)
CAPTURED = datetime.datetime(2026, 10, 2, 16, 0, 0)
SHA = "ab" * 32


def _datasets(drop: Optional[str] = None) -> list[dict[str, object]]:
    names = [
        "commerce_postgres",
        "payment_attempts",
        "refund_ledger",
        "order_handoff_outbox",
        "notification_outbox",
        "capacity_reservations",
        "ops_exception_queue",
    ]
    return [{"name": name, "byte_size": 128, "sha256": SHA} for name in names if name != drop]


def _manifest(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "backup_id": "rehearsal-20261002",
        "captured_at": CAPTURED,
        "credentials_included": False,
        "datasets": _datasets(),
    }
    body.update(overrides)
    return body


@pytest.mark.no_db
def test_restore_state_machine_replays_each_effect_once_and_keeps_checkout_gated() -> None:
    state = open_restore(RESTORE_ID, later_payment=True, later_refund=True)
    assert state.checkout == "gated"
    assert state.ops_reachable is False
    assert gate_reason(state) == (
        "Restored checkout stays gated until provider, order, stock, and capacity are reconciled"
    )
    assert all(count == 0 for count in state.effects.values())

    blocked = replay_effect(state, "payment", "pay-key-1", provider_verified=False)
    assert blocked[1] == "needs_provider"
    assert blocked[0].effects["payment"] == 0

    paid = replay_effect(state, "payment", "pay-key-1", provider_verified=True)
    assert paid[1] == "applied"
    assert paid[0].effects["payment"] == 1
    resumed = resume_recovery(paid[0])
    assert replay_effect(resumed, "payment", "pay-key-1", provider_verified=True)[1] == "duplicate"
    other_key = replay_effect(resumed, "payment", "pay-key-2", provider_verified=True)
    assert other_key[1] == "duplicate"
    assert other_key[0].effects["payment"] == 1

    refunded = replay_effect(other_key[0], "refund", "refund-key-1", provider_verified=True)
    ordered = replay_effect(refunded[0], "order", "order-key-1", provider_verified=False)
    posted = replay_effect(ordered[0], "operational_posting", "post-key-1", provider_verified=False)
    mailed = replay_effect(posted[0], "email", "mail-key-1", provider_verified=False)
    assert mailed[0].effects == {
        "payment": 1,
        "refund": 1,
        "order": 1,
        "operational_posting": 1,
        "email": 1,
    }
    assert (
        replay_effect(mailed[0], "email", "mail-key-1", provider_verified=False)[0].effects["email"]
        == 1
    )
    refundless = open_restore("snap-refundless", later_payment=True, later_refund=False)
    rejected = replay_effect(refundless, "refund", "refund-key-9", provider_verified=True)
    assert rejected[1] == "rejected"

    early_provider = reconcile_truth(state, "provider", provider_verified=True)
    assert early_provider[1] == "needs_effect"
    stock = reconcile_truth(mailed[0], "stock", provider_verified=False)
    capacity = reconcile_truth(stock[0], "capacity", provider_verified=False)
    assert capacity[0].effects == mailed[0].effects
    assert capacity[0].checkout == "gated"
    provider = reconcile_truth(capacity[0], "provider", provider_verified=False)
    assert provider[1] == "needs_provider"
    provider_ok = reconcile_truth(capacity[0], "provider", provider_verified=True)
    order_ok = reconcile_truth(provider_ok[0], "order", provider_verified=False)
    assert order_ok[0].truths == {
        "provider": "reconciled",
        "order": "reconciled",
        "stock": "reconciled",
        "capacity": "reconciled",
    }
    assert with_ops(order_ok[0], False).checkout == "gated"
    assert gate_reason(with_ops(order_ok[0], False)) == (
        "Firstout is a required dependency. Checkout stays gated until operations are reachable."
    )
    opened = with_ops(order_ok[0], True)
    assert opened.checkout == "open"
    assert (
        replay_effect(opened, "email", "mail-key-2", provider_verified=False)[0].effects["email"]
        == 1
    )
    assert reconcile_truth(opened, "stock", provider_verified=False)[1] == "already_reconciled"


@pytest.mark.no_db
def test_reconstruction_counts_repaired_audits_and_does_not_hide_a_duplicate() -> None:
    rows = [
        RowView("restore:snap-20261002:payment", "open"),
        RowView("restore:snap-20261002:order", "open"),
        RowView("restore:snap-20261002:stock", "resolved"),
        RowView("restore:snap-20261002:capacity", "resolved"),
    ]
    audits = [
        AuditView("pay-key-1", "repaired", "effect:payment"),
        AuditView("pay-key-2", "repaired", "effect:payment"),
        AuditView("pay-key-3", "already_resolved", "effect:payment"),
    ]
    state = state_from_rows(RESTORE_ID, rows, audits, ops_reachable=False)
    assert state.later_payment is True
    assert state.later_refund is False
    assert state.effects["payment"] == 2
    assert state.truths["stock"] == "reconciled"
    assert state.truths["provider"] == "pending"
    assert "pay-key-3" in state.seen_keys


@pytest.mark.no_db
def test_backup_rehearsal_records_a_proposal_and_alerts_without_secrets() -> None:
    assert PROPOSED_BACKUP_POLICY["agreed_sla"] is False
    assert PROPOSED_BACKUP_POLICY["status"] == "proposal"
    assert PROPOSED_BACKUP_POLICY["daily_copies"] == 14
    fresh = assess_backup(_manifest(), NOW)
    assert fresh.ok is True
    assert fresh.code == "ok"
    measured = measure_clocks(
        captured_at=CAPTURED,
        now=NOW,
        operator_started_at=NOW,
        operator_finished_at=NOW + datetime.timedelta(minutes=12),
    )
    assert measured["backup_age_ms"] == 20 * 60 * 60 * 1000
    assert measured["rehearsal_elapsed_ms"] == 12 * 60 * 1000
    assert measured["within_proposed_recovery_point"] is True
    assert measured["within_proposed_restoration"] is True
    assert measured["live_restore"] is False
    assert measured["agreed_sla"] is False
    slow = measure_clocks(
        captured_at=CAPTURED,
        now=NOW,
        operator_started_at=NOW,
        operator_finished_at=NOW + datetime.timedelta(hours=5),
    )
    assert slow["within_proposed_restoration"] is False

    missing = assess_backup(_manifest(datasets=_datasets("payment_attempts")), NOW)
    assert missing.code == "missing"
    assert missing.alert is not None
    assert missing.alert.context["dataset"] == "payment_attempts"
    stale = assess_backup(_manifest(captured_at=NOW - datetime.timedelta(hours=25)), NOW)
    assert stale.code == "stale"
    assert stale.message is not None
    assert "proposal" in stale.message
    assert "agreed SLA" in stale.message
    corrupt = assess_backup(_manifest(credentials_included=True), NOW)
    assert corrupt.code == "corrupt"
    leaked = route_alert(
        "spending",
        {
            "customer_email": "payer@example.test",
            "amount_minor": 115000,
            "token": "secret-token",
            "backup_id": "not an id",
        },
    )
    encoded = str(leaked.context)
    assert "payer@example.test" not in encoded
    assert "secret-token" not in encoded
    assert "115000" not in encoded
    assert leaked.context["agreed_sla"] is False
    assert leaked.context["live_restore"] is False


def _api_datasets(drop: Optional[str] = None) -> list[dict[str, Any]]:
    return [
        {"name": item["name"], "byte_size": item["byte_size"], "sha256": item["sha256"]}
        for item in _datasets(drop)
    ]


async def _login(client: AsyncClient, email: str, password: str) -> None:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_restore_uses_exception_queue_and_blocks_checkout_until_reconciled(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = await async_db.scalar(select(Team.id))
    assert company_id is not None
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id), raising=False)
    monkeypatch.setattr(settings, "ops_commerce_token", "storefront-test-token", raising=False)
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test", raising=False)
    ops_headers = {
        "Authorization": "Bearer storefront-test-token",
        "X-Ops-Company-ID": str(company_id),
    }

    opened = await owner_client.post(
        "/api/v1/storefront/exceptions/recovery",
        json={"restore_id": RESTORE_ID, "later_payment": True, "later_refund": True},
    )
    assert opened.status_code == 200
    body = opened.json()
    assert body["checkout"] == "gated"
    assert body["checkout_allowed"] is False
    assert body["live_restore"] is False
    assert body["agreed_sla"] is False
    assert body["firstout_dependency"] == "required"
    assert body["proposal"]["daily_copies"] == 14
    assert body["proposal"]["status"] == "proposal"
    assert body["effects"] == {
        "payment": 0,
        "refund": 0,
        "order": 0,
        "operational_posting": 0,
        "email": 0,
    }
    assert set(body["truths"]) == {"provider", "order", "stock", "capacity"}
    assert all(value == "pending" for value in body["truths"].values())

    again = await owner_client.post(
        "/api/v1/storefront/exceptions/recovery",
        json={"restore_id": RESTORE_ID, "later_payment": True, "later_refund": True},
    )
    assert again.status_code == 200
    count = await async_db.scalar(
        select(func.count())
        .select_from(StorefrontCommerceException)
        .where(StorefrontCommerceException.correlation_id == f"storefront:restore:{RESTORE_ID}")
    )
    assert count == 5

    safety = await owner_client.get("/api/v1/ops-commerce/v1/checkout-safety", headers=ops_headers)
    assert safety.status_code == 200
    assert safety.json()["checkout_allowed"] is False
    assert "provider, order, stock, and capacity" in safety.json()["reason"]

    unverified = await owner_client.post(
        "/api/v1/storefront/exceptions/recovery/replay",
        json={
            "restore_id": RESTORE_ID,
            "effect": "payment",
            "idempotency_key": "pay-key-1",
            "provider_verified": False,
            "reason": "Callback arrived before provider verification",
        },
    )
    assert unverified.status_code == 400

    async def _replay(effect: str, key: str, *, verified: bool = False) -> dict[str, Any]:
        resp = await owner_client.post(
            "/api/v1/storefront/exceptions/recovery/replay",
            json={
                "restore_id": RESTORE_ID,
                "effect": effect,
                "idempotency_key": key,
                "provider_verified": verified,
                "reason": f"Apply {effect} once during restore",
            },
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    paid = await _replay("payment", "pay-key-1", verified=True)
    assert paid["effects"]["payment"] == 1
    replayed = await _replay("payment", "pay-key-1", verified=True)
    assert replayed["effects"]["payment"] == 1
    second_key = await _replay("payment", "pay-key-2", verified=True)
    assert second_key["effects"]["payment"] == 1
    refunded = await _replay("refund", "refund-key-1", verified=True)
    ordered = await _replay("order", "order-key-1")
    posted = await _replay("operational_posting", "post-key-1")
    mailed = await _replay("email", "mail-key-1")
    assert mailed["effects"]["email"] == 1
    assert refunded["effects"]["refund"] == 1
    assert ordered["effects"]["order"] == 1
    assert posted["effects"]["operational_posting"] == 1
    mailed_again = await _replay("email", "mail-key-1")
    assert mailed_again["effects"]["email"] == 1

    async def _reconcile(truth: str, key: str, *, verified: bool = False) -> Any:
        return await owner_client.post(
            "/api/v1/storefront/exceptions/recovery/reconcile",
            json={
                "restore_id": RESTORE_ID,
                "truth": truth,
                "idempotency_key": key,
                "provider_verified": verified,
                "reason": f"Reconcile {truth} for the restored snapshot",
            },
        )

    stock = await _reconcile("stock", "truth-stock-1")
    assert stock.status_code == 200
    assert stock.json()["effects"] == mailed["effects"]
    assert stock.json()["truths"]["stock"] == "reconciled"
    capacity = await _reconcile("capacity", "truth-capacity-1")
    assert capacity.status_code == 200
    assert capacity.json()["checkout_allowed"] is False
    needs_provider = await _reconcile("provider", "truth-provider-1", verified=False)
    assert needs_provider.status_code == 400
    provider = await _reconcile("provider", "truth-provider-1", verified=True)
    assert provider.status_code == 200
    order = await _reconcile("order", "truth-order-1")
    assert order.status_code == 200
    assert order.json()["truths"]["order"] == "reconciled"
    assert order.json()["checkout_allowed"] is False

    listed = await owner_client.get("/api/v1/storefront/exceptions")
    restore_rows = [
        item
        for item in listed.json()["items"]
        if item["correlation_id"] == f"storefront:restore:{RESTORE_ID}"
    ]
    by_kind = {item["kind"]: item for item in restore_rows}
    assert by_kind["stale_sync"]["repair_count"] == 0
    assert by_kind["stale_sync"]["status"] == "resolved"
    assert by_kind["missing_operational_paid_order"]["repair_count"] == 3
    assert by_kind["unknown_payment"]["repair_count"] == 1

    cleared = await owner_client.get("/api/v1/ops-commerce/v1/checkout-safety", headers=ops_headers)
    assert cleared.json()["checkout_allowed"] is True
    still_down = await owner_client.get(
        f"/api/v1/storefront/exceptions/recovery/{RESTORE_ID}",
        params={"ops_reachable": False},
    )
    assert still_down.json()["checkout_allowed"] is False
    assert "Firstout" in still_down.json()["reason"]
    reachable = await owner_client.get(
        f"/api/v1/storefront/exceptions/recovery/{RESTORE_ID}",
        params={"ops_reachable": True},
    )
    assert reachable.json()["checkout_allowed"] is True
    assert reachable.json()["live_restore"] is False

    missing = await owner_client.post(
        "/api/v1/storefront/exceptions/recovery/backup-check",
        json={
            "backup_id": "rehearsal-20261002",
            "captured_at": CAPTURED.isoformat(),
            "credentials_included": False,
            "datasets": _api_datasets("notification_outbox"),
            "now": NOW.isoformat(),
        },
    )
    assert missing.status_code == 200
    assert missing.json()["ok"] is False
    assert missing.json()["code"] == "missing"
    assert missing.json()["live_restore"] is False
    assert missing.json()["agreed_sla"] is False
    assert "payer@example.test" not in str(missing.json()["context"])
    assert missing.json()["context"]["dataset"] == "notification_outbox"

    fresh = await owner_client.post(
        "/api/v1/storefront/exceptions/recovery/backup-check",
        json={
            "backup_id": "rehearsal-20261002",
            "captured_at": CAPTURED.isoformat(),
            "credentials_included": False,
            "datasets": _api_datasets(),
            "now": NOW.isoformat(),
            "operator_started_at": NOW.isoformat(),
            "operator_finished_at": (NOW + datetime.timedelta(minutes=12)).isoformat(),
        },
    )
    assert fresh.status_code == 200
    assert fresh.json()["ok"] is True
    assert fresh.json()["measured"]["backup_age_ms"] == 20 * 60 * 60 * 1000
    assert fresh.json()["measured"]["rehearsal_elapsed_ms"] == 12 * 60 * 1000
    assert fresh.json()["measured"]["live_restore"] is False
    assert fresh.json()["proposal"]["recovery_point_hours"] == 24
    assert fresh.json()["proposal"]["restoration_hours_after_operator_start"] == 4

    spending = await owner_client.post(
        "/api/v1/storefront/exceptions/recovery/alerts",
        json={"route": "spending"},
    )
    assert spending.status_code == 200
    assert spending.json()["queue_class"] == "terminal"
    assert "customer or payment data" in spending.json()["context"]["message"]
    assert spending.json()["context"]["live_restore"] is False

    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    denied = await async_client.post(
        "/api/v1/storefront/exceptions/recovery",
        json={"restore_id": "snap-warehouse", "later_payment": True, "later_refund": False},
    )
    assert denied.status_code == 403

    await _login(async_client, "till@example.com", settings.seed_till_password)
    till_payment = await async_client.post(
        "/api/v1/storefront/exceptions/recovery/replay",
        json={
            "restore_id": RESTORE_ID,
            "effect": "payment",
            "idempotency_key": "till-pay-key",
            "provider_verified": True,
            "reason": "Till must not replay a payment",
        },
    )
    assert till_payment.status_code == 403

    await _login(async_client, "books@example.com", settings.seed_books_password)
    books_stock = await async_client.post(
        "/api/v1/storefront/exceptions/recovery/reconcile",
        json={
            "restore_id": RESTORE_ID,
            "truth": "stock",
            "idempotency_key": "books-stock-key",
            "provider_verified": False,
            "reason": "Books must not reconcile stock",
        },
    )
    assert books_stock.status_code == 403
    books_payment = await async_client.post(
        "/api/v1/storefront/exceptions/recovery/replay",
        json={
            "restore_id": RESTORE_ID,
            "effect": "payment",
            "idempotency_key": "pay-key-1",
            "provider_verified": True,
            "reason": "Books replays the same verified payment",
        },
    )
    assert books_payment.status_code == 200
    assert books_payment.json()["effects"]["payment"] == 1
