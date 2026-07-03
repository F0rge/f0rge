"""HTTP-level tests for the entries router (CRUD + auth gating).

No mocks of app code. create_entry/update_entry call through to the real
obsidian vault writer (app.services.obsidian.write_daily_file), which no-ops
safely when settings.vault_path is unwritable/unset -- exercised for real,
not stubbed out, per feedback_no_mocks_at_seam_under_test.md.
"""

from __future__ import annotations

import datetime

import bcrypt
import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.entries import _period_of_day

TEST_PIN = "1234"

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


@pytest.fixture(autouse=True)
def known_pin(monkeypatch: pytest.MonkeyPatch) -> str:
    hashed = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(settings, "pin_hash", hashed)
    return TEST_PIN


@pytest.fixture
async def authed_client(async_client: AsyncClient) -> AsyncClient:
    """The house async_client, logged in via a real login round-trip."""
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 200
    return async_client


# ---------------------------------------------------------------------------
# Auth gating -- every verb requires a session (router-level dependency)
# ---------------------------------------------------------------------------


async def test_create_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert resp.status_code == 401


async def test_list_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/entries")
    assert resp.status_code == 401


async def test_get_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/entries/2026-02-01")
    assert resp.status_code == 401


async def test_update_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.put("/api/v1/entries/2026-02-01", json={"overall": 5})
    assert resp.status_code == 401


async def test_delete_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.delete("/api/v1/entries/2026-02-01")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


async def test_get_missing_date_404(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/entries/2026-03-15")
    assert resp.status_code == 404


async def test_update_missing_date_404(authed_client: AsyncClient) -> None:
    resp = await authed_client.put("/api/v1/entries/2026-03-15", json={"overall": 5})
    assert resp.status_code == 404


async def test_delete_missing_date_404(authed_client: AsyncClient) -> None:
    resp = await authed_client.delete("/api/v1/entries/2026-03-15")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_get_invalid_date_format_422(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/entries/not-a-date")
    assert resp.status_code == 422


async def test_create_missing_required_field_422(authed_client: AsyncClient) -> None:
    payload = dict(_VALID_PAYLOAD)
    del payload["overall"]
    resp = await authed_client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_entry_201_shape(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["date"] == "2026-02-01"
    assert body["overall"] == 3
    assert body["schema_version"] == 3
    assert body["photos"] == []
    assert body["effective_flags"] == []
    assert body["photo_derived_flags"] == []
    assert body["user_added_flags"] == []
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_duplicate_date_409(authed_client: AsyncClient) -> None:
    first = await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert first.status_code == 201

    second = await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert second.status_code == 409


async def test_create_entry_persists_and_is_gettable(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-02-01"


async def test_create_entry_strips_tz_aware_entry_time(authed_client: AsyncClient) -> None:
    """entry_time sent as tz-aware ISO (+02:00) is stored/returned as naive UTC.

    Regression guard for project_datetime_tz_convention.md -- proves the
    strip-at-boundary validator holds end-to-end through the real HTTP path,
    not just as a schema-unit assertion.
    """
    payload = dict(_VALID_PAYLOAD)
    payload["entry_time"] = "2026-02-01T10:30:00+02:00"  # == 08:30 UTC

    resp = await authed_client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["entry_time"] == "2026-02-01T08:30:00"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_entries_empty(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/entries")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_entries_returns_created(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    resp = await authed_client.get("/api/v1/entries")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["date"] == "2026-02-01"


async def test_list_entries_filters_by_month(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    other = dict(_VALID_PAYLOAD)
    other["date"] = "2026-03-01"
    await authed_client.post("/api/v1/entries", json=other)

    resp = await authed_client.get("/api/v1/entries", params={"month": "2026-02"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["date"] == "2026-02-01"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_entry_200_and_persists(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    update_resp = await authed_client.put(
        "/api/v1/entries/2026-02-01", json={"overall": 7, "notes": "felt better"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["overall"] == 7
    assert update_resp.json()["notes"] == "felt better"

    # Re-GET proves the write persisted, not just the response of the PUT call.
    get_resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert get_resp.status_code == 200
    assert get_resp.json()["overall"] == 7
    assert get_resp.json()["notes"] == "felt better"


async def test_update_entry_partial_leaves_other_fields_unchanged(
    authed_client: AsyncClient,
) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    await authed_client.put("/api/v1/entries/2026-02-01", json={"bloating": 9})

    resp = await authed_client.get("/api/v1/entries/2026-02-01")
    body = resp.json()
    assert body["bloating"] == 9
    assert body["overall"] == 3  # unchanged from _VALID_PAYLOAD


async def test_update_entry_accepts_tz_aware_entry_time_without_500(
    authed_client: AsyncClient,
) -> None:
    """PUT with a tz-aware entry_time does not 500 (asyncpg would reject an
    offset-aware datetime bound to the tz-naive column -- see
    project_datetime_tz_convention.md). The tz-strip validator on EntryUpdate
    runs uniformly with EntryCreate's even though the value is discarded
    afterward (see test_update_entry_always_restamps_entry_time_to_now below)
    -- this test only proves that discard path doesn't blow up the request.
    """
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    resp = await authed_client.put(
        "/api/v1/entries/2026-02-01",
        json={"entry_time": "2026-02-01T23:00:00+01:00"},  # == 22:00 UTC
    )
    assert resp.status_code == 200
    # entry_time is naive (no offset suffix) -- proves no tz-aware datetime
    # reached asyncpg.
    assert "+" not in resp.json()["entry_time"]


async def test_update_entry_always_restamps_entry_time_to_now(
    authed_client: AsyncClient,
) -> None:
    """entry_time/period_of_day are server-owned "last edited" metadata, not a
    caller-settable field, despite EntryUpdate declaring them (see the
    comment on EntryUpdate.entry_time). Every consumer -- the history page's
    "Last logged at" label, the Obsidian vault's "Logged at" row, insights'
    correlation-feature exclusion list -- treats the field as edit-time
    metadata. A caller-supplied entry_time on PUT must be silently ignored
    and replaced with the server's current time, matching create_entry's
    period_of_day derivation for whatever entry_time actually lands.
    """
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    before = datetime.datetime.utcnow()
    resp = await authed_client.put(
        "/api/v1/entries/2026-02-01",
        # Caller-chosen value, deliberately far from "now" so any leak is unmistakable.
        json={"entry_time": "2020-01-01T00:00:00"},
    )
    after = datetime.datetime.utcnow()

    assert resp.status_code == 200
    body = resp.json()
    stamped = datetime.datetime.fromisoformat(body["entry_time"])
    assert before <= stamped <= after
    assert body["period_of_day"] == _period_of_day(stamped)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_entry_204_then_404_on_reget(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    delete_resp = await authed_client.delete("/api/v1/entries/2026-02-01")
    assert delete_resp.status_code == 204

    get_resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert get_resp.status_code == 404


async def test_delete_entry_removes_from_list(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    await authed_client.delete("/api/v1/entries/2026-02-01")

    resp = await authed_client.get("/api/v1/entries")
    assert resp.json() == []
