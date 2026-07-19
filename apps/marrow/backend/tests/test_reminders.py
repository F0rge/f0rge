"""Tests for the dose reminder scheduler (#390).

The tick is exercised directly with an injected ``now`` (httpx ASGITransport
never runs lifespan, so the background loop is not started here) against the
savepoint ``async_db`` session via a patched ``async_session_maker`` — the
same cross-session pattern as tag delivery tests.
"""

from __future__ import annotations

import datetime
import uuid
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import UserSettings
from app.services import reminders
from app.services.reminders import derive_slots, run_reminder_tick
from f0rge_db.tenant import apply_session_user_id
from tests.conftest import authed_user_id
from tests.helpers import create_treatment, signup_client

UTC = datetime.timezone.utc
# Europe/Luxembourg is UTC+2 (CEST) on these dates.
IN_WINDOW = datetime.datetime(2026, 7, 18, 7, 5, tzinfo=UTC)  # 09:05 local
STALE = datetime.datetime(2026, 7, 18, 7, 20, tzinfo=UTC)  # 09:20 local — window closed
TODAY = datetime.date(2026, 7, 18)


# ---------------------------------------------------------------------------
# Slot derivation (pure)
# ---------------------------------------------------------------------------


def _t(hour: int, minute: int = 0) -> datetime.time:
    return datetime.time(hour, minute)


def test_derive_slots_one_dose():
    assert derive_slots(1) == [_t(9)]


def test_derive_slots_two_doses():
    assert derive_slots(2) == [_t(9), _t(21)]


def test_derive_slots_three_doses():
    assert derive_slots(3) == [_t(9), _t(14), _t(21)]


def test_derive_slots_five_doses_evenly_spaced():
    assert derive_slots(5) == [_t(9), _t(12), _t(15), _t(18), _t(21)]


def test_derive_slots_override_wins_and_is_sorted():
    assert derive_slots(2, ["20:30", "08:00"]) == [_t(8), _t(20, 30)]


# ---------------------------------------------------------------------------
# Tick behavior against the database
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def signed_up_client(async_db: AsyncSession) -> AsyncClient:
    """A freshly signed-up (non-default) user — the RLS-relevant case."""
    return await signup_client(async_db, f"rem_{uuid.uuid4().hex[:8]}@example.com")


async def _notifications(client: AsyncClient) -> list[dict]:
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_tick_fires_only_slot_in_window_for_non_default_user(
    signed_up_client: AsyncClient,
):
    treatment_id = await create_treatment(signed_up_client, doses_per_day=2)

    fired = await run_reminder_tick(now=IN_WINDOW)
    assert fired == 1

    # Frontend bell path: the row is visible to that user via the API.
    notes = await _notifications(signed_up_client)
    assert len(notes) == 1
    note = notes[0]
    assert note["type"] == "dose_reminder"
    assert note["payload"]["treatment_id"] == str(treatment_id)
    assert note["payload"]["treatment_name"] == "Rifaximin"
    assert note["payload"]["slot"] == 1
    assert note["payload"]["date"] == TODAY.isoformat()
    assert "dedupe_key" not in note

    unread = await signed_up_client.get("/api/v1/notifications/unread-count")
    assert unread.json()["count"] == 1


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_tick_stale_slot_does_not_fire(signed_up_client: AsyncClient):
    await create_treatment(signed_up_client, doses_per_day=1)

    fired = await run_reminder_tick(now=STALE)
    assert fired == 0
    assert await _notifications(signed_up_client) == []


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_doses_taken_suppresses_slot(signed_up_client: AsyncClient):
    treatment_id = await create_treatment(signed_up_client, doses_per_day=1)
    logged = await signed_up_client.put(
        f"/api/v1/treatments/{treatment_id}/log",
        json={"date": TODAY.isoformat(), "doses_taken": 1},
    )
    assert logged.status_code == 200

    fired = await run_reminder_tick(now=IN_WINDOW)
    assert fired == 0
    assert await _notifications(signed_up_client) == []


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_double_tick_dedupes_to_single_row(signed_up_client: AsyncClient):
    await create_treatment(signed_up_client, doses_per_day=2)

    assert await run_reminder_tick(now=IN_WINDOW) == 1
    assert await run_reminder_tick(now=IN_WINDOW) == 0

    assert len(await _notifications(signed_up_client)) == 1


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_timezone_honored(async_db: AsyncSession):
    """Same instant: 09:05 in Auckland (fires, next-day date) vs 23:05 in Luxembourg (stale)."""
    auckland_client = await signup_client(async_db, f"rem_{uuid.uuid4().hex[:8]}@example.com")
    lux_client = await signup_client(async_db, f"rem_{uuid.uuid4().hex[:8]}@example.com")
    await create_treatment(auckland_client, doses_per_day=2)
    await create_treatment(lux_client, doses_per_day=2)

    auckland_id = await authed_user_id(auckland_client)
    await apply_session_user_id(async_db, auckland_id)
    async_db.add(UserSettings(user_id=auckland_id, timezone="Pacific/Auckland"))
    await async_db.flush()

    # 2026-07-18 21:05 UTC = 2026-07-19 09:05 NZST = 2026-07-18 23:05 CEST.
    now = datetime.datetime(2026, 7, 18, 21, 5, tzinfo=UTC)
    assert now.astimezone(ZoneInfo("Pacific/Auckland")).time() == datetime.time(9, 5)

    fired = await run_reminder_tick(now=now)
    assert fired == 1

    auckland_notes = await _notifications(auckland_client)
    assert len(auckland_notes) == 1
    assert auckland_notes[0]["payload"]["slot"] == 1
    assert auckland_notes[0]["payload"]["date"] == "2026-07-19"

    assert await _notifications(lux_client) == []


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_one_users_failure_does_not_stop_other_users(
    async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A per-user savepoint isolates a failing tick from everyone else's reminders."""
    client_a = await signup_client(async_db, f"rem_{uuid.uuid4().hex[:8]}@example.com")
    client_b = await signup_client(async_db, f"rem_{uuid.uuid4().hex[:8]}@example.com")
    await create_treatment(client_a, doses_per_day=2)
    await create_treatment(client_b, doses_per_day=2)

    # Poison whichever user is ticked first; the other must still be reminded.
    calls = {"n": 0}
    real_derive_slots = reminders.derive_slots

    def flaky_derive_slots(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_derive_slots(*args, **kwargs)

    monkeypatch.setattr(reminders, "derive_slots", flaky_derive_slots)

    fired = await run_reminder_tick(now=IN_WINDOW)

    assert calls["n"] == 2  # both users were attempted
    assert fired == 1
    notes_a = await _notifications(client_a)
    notes_b = await _notifications(client_b)
    assert sorted([len(notes_a), len(notes_b)]) == [0, 1]
