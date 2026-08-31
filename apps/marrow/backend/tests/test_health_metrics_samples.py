"""Tests for POST /health-metrics/samples — per-user HealthKit ingest (#389)."""

from __future__ import annotations

import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_db.auth_context import user_id_ctx
from app.database import get_db
from app.main import app
from app.models.health_metrics import HealthMetric
from f0rge_db.tenant import apply_session_user_id
from tests.conftest import authed_user_id
from tests.helpers import signup_client, signup_payload

PASSWORD = "samples-test-pass-12"
SAMPLES_URL = "/api/v1/health-metrics/samples"


async def _rows_for_user(
    async_db: AsyncSession, user_id: uuid.UUID, date: datetime.date
) -> list[HealthMetric]:
    token = user_id_ctx.set(user_id)
    try:
        await apply_session_user_id(async_db, user_id)
        result = await async_db.execute(select(HealthMetric).where(HealthMetric.date == date))
        return list(result.scalars().all())
    finally:
        user_id_ctx.reset(token)


async def test_same_batch_twice_is_idempotent(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    batch = {
        "samples": [
            {"date": "2026-07-01", "hrv_mean": 55.2, "resting_hr": 52.0},
            {"date": "2026-07-02", "hrv_mean": 60.1},
        ]
    }
    first = await authed_client.post(SAMPLES_URL, json=batch)
    assert first.status_code == 200
    assert first.json() == {"status": "ok", "dates_upserted": 2}

    second = await authed_client.post(SAMPLES_URL, json=batch)
    assert second.status_code == 200
    assert second.json() == {"status": "ok", "dates_upserted": 2}

    user_id = await authed_user_id(authed_client)
    rows = await _rows_for_user(async_db, user_id, datetime.date(2026, 7, 1))
    assert len(rows) == 1
    assert rows[0].hrv_mean == 55.2
    assert rows[0].resting_hr == 52.0
    assert rows[0].source == "ios_healthkit"


async def test_partial_batches_merge_fields(authed_client: AsyncClient) -> None:
    first = await authed_client.post(
        SAMPLES_URL, json={"samples": [{"date": "2026-07-03", "hrv_mean": 48.5}]}
    )
    assert first.status_code == 200

    second = await authed_client.post(
        SAMPLES_URL, json={"samples": [{"date": "2026-07-03", "resting_hr": 55.0}]}
    )
    assert second.status_code == 200

    row = await authed_client.get("/api/v1/health-metrics/2026-07-03")
    assert row.status_code == 200
    body = row.json()
    assert body["hrv_mean"] == 48.5
    assert body["resting_hr"] == 55.0


async def test_empty_samples_rejected(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(SAMPLES_URL, json={"samples": []})
    assert resp.status_code == 422


async def test_two_users_see_only_their_own_samples(async_db: AsyncSession) -> None:
    client_a = await signup_client(async_db, "samples-a@example.com", PASSWORD)
    client_b = await signup_client(async_db, "samples-b@example.com", PASSWORD)
    try:
        posted_a = await client_a.post(
            SAMPLES_URL, json={"samples": [{"date": "2026-07-04", "hrv_mean": 41.0}]}
        )
        assert posted_a.status_code == 200

        posted_b = await client_b.post(
            SAMPLES_URL, json={"samples": [{"date": "2026-07-05", "resting_hr": 60.0}]}
        )
        assert posted_b.status_code == 200

        own_a = await client_a.get("/api/v1/health-metrics/2026-07-04")
        assert own_a.status_code == 200
        assert own_a.json()["hrv_mean"] == 41.0

        own_b = await client_b.get("/api/v1/health-metrics/2026-07-05")
        assert own_b.status_code == 200
        assert own_b.json()["resting_hr"] == 60.0

        assert (await client_a.get("/api/v1/health-metrics/2026-07-05")).status_code == 404
        assert (await client_b.get("/api/v1/health-metrics/2026-07-04")).status_code == 404
    finally:
        await client_a.aclose()
        await client_b.aclose()
        app.dependency_overrides.pop(get_db, None)


async def test_bearer_only_samples_post(async_client: AsyncClient) -> None:
    signup = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload("samples-bearer@example.com", PASSWORD),
    )
    assert signup.status_code == 200
    async_client.cookies.clear()

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "samples-bearer@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    assert token
    async_client.cookies.clear()

    headers = {"Authorization": f"Bearer {token}"}
    posted = await async_client.post(
        SAMPLES_URL, json={"samples": [{"date": "2026-07-06", "steps": 8000}]}, headers=headers
    )
    assert posted.status_code == 200

    fetched = await async_client.get("/api/v1/health-metrics/2026-07-06", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["steps"] == 8000


async def test_manual_import_source_is_stored(authed_client: AsyncClient) -> None:
    posted = await authed_client.post(
        SAMPLES_URL,
        json={
            "samples": [
                {
                    "date": "2026-08-01",
                    "sleep_hours": 7.5,
                    "hrv_mean": 45.0,
                    "source": "manual_import",
                }
            ]
        },
    )
    assert posted.status_code == 200
    row = await authed_client.get("/api/v1/health-metrics/2026-08-01")
    assert row.status_code == 200
    body = row.json()
    assert body["source"] == "manual_import"
    assert body["sleep_hours"] == 7.5
    assert body["hrv_mean"] == 45.0


async def test_unknown_source_rejected(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(
        SAMPLES_URL,
        json={"samples": [{"date": "2026-08-02", "steps": 100, "source": "fitbit"}]},
    )
    assert resp.status_code == 400


async def test_range_lists_imported_days(authed_client: AsyncClient) -> None:
    await authed_client.post(
        SAMPLES_URL,
        json={
            "samples": [
                {"date": "2026-08-10", "sleep_hours": 8.0, "source": "manual_import"},
                {"date": "2026-08-11", "steps": 9000, "source": "manual_import"},
            ]
        },
    )
    resp = await authed_client.get(
        "/api/v1/health-metrics/range",
        params={"start": "2026-08-10", "end": "2026-08-11"},
    )
    assert resp.status_code == 200
    dates = {row["date"] for row in resp.json()}
    assert dates == {"2026-08-10", "2026-08-11"}


async def test_range_rejects_inverted_dates(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(
        "/api/v1/health-metrics/range",
        params={"start": "2026-08-11", "end": "2026-08-10"},
    )
    assert resp.status_code == 400
