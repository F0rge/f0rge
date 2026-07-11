"""Atomicity tests for EntryOrchestrator.create_entry/update_entry (#225 Rule 6.4).

Before this fix, the entry write and the tracker-log sync landed in two
separate commits (``EntryService.commit_entry`` committed the entry, then
``sync_seed_tracker_log_from_entry`` committed again). A failure in the
second commit left a half-written entry already persisted. Both now run
inside a single ``unit_of_work`` -- these tests fail-inject the tracker-sync
step and prove nothing survives the rollback.

Mocks only the tracker-sync seam (the boundary under failure injection), not
the code path under test itself -- see feedback_no_mocks_at_seam_under_test.
"""

from __future__ import annotations

import datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_db.auth_context import user_id_ctx
from app.database import get_db
from app.main import app
from app.models.entry import Entry
from f0rge_db.tenant import apply_session_user_id

_ATOMICITY_EMAIL = "atomicity-test@example.com"
_ATOMICITY_PASSWORD = "test-password-12"
_ENTRY_DATE = datetime.date(2026, 2, 1)

_VALID_PAYLOAD = {
    "date": "2026-02-01",
    "overall": 3,
    "bloating": 1,
    "stool_status": "normal",
    "joint_pain": 0,
    "neuro": 0,
    "sleep_quality": 4,
    "stress": 2,
    "diet_risk": "",
    "supplements": "",
    "sick": False,
}


@pytest_asyncio.fixture
async def error_client(async_db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Same wiring as the house ``async_client`` fixture, but with
    ``raise_app_exceptions=False`` so an unhandled exception in a failure-injected
    write path comes back as a real 500 response instead of re-raising into the
    test -- needed to assert on the HTTP status code."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        user_id = user_id_ctx.get()
        if user_id is not None:
            await apply_session_user_id(async_db, user_id)
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def authed_error_client(error_client: AsyncClient) -> AsyncClient:
    resp = await error_client.post(
        "/api/v1/auth/signup",
        json={"email": _ATOMICITY_EMAIL, "password": _ATOMICITY_PASSWORD},
    )
    assert resp.status_code == 200
    return error_client


async def _boom(db: AsyncSession, entry: object) -> None:
    raise RuntimeError("tracker sync exploded")


async def test_create_entry_rolls_back_on_tracker_sync_failure(
    authed_error_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.entry_orchestrator.sync_seed_tracker_log_from_entry", _boom)

    resp = await authed_error_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert resp.status_code == 500

    entry = (
        await async_db.execute(select(Entry).where(Entry.date == _ENTRY_DATE))
    ).scalar_one_or_none()
    assert entry is None


async def test_update_entry_rolls_back_on_tracker_sync_failure(
    authed_error_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_resp = await authed_error_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert create_resp.status_code == 201

    monkeypatch.setattr("app.services.entry_orchestrator.sync_seed_tracker_log_from_entry", _boom)

    resp = await authed_error_client.put(
        f"/api/v1/entries/{_ENTRY_DATE.isoformat()}",
        json={"overall": 9, "notes": "should not persist"},
    )
    assert resp.status_code == 500

    entry = (
        await async_db.execute(select(Entry).where(Entry.date == _ENTRY_DATE))
    ).scalar_one_or_none()
    assert entry is not None
    assert entry.overall == 3
    assert entry.notes is None
