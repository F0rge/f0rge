"""HTTP-level tests for the entries router (CRUD + auth gating).

No mocks of app code.
"""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient

from app.services.entries import _period_of_day
from app.utils.dates import local_today

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
    del payload["date"]
    resp = await authed_client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 422


@pytest.mark.parametrize(
    ("field", "day"),
    [
        ("overall", "2026-02-01"),
        ("bloating", "2026-02-02"),
        ("sleep_quality", "2026-02-03"),
        ("stress", "2026-02-04"),
    ],
)
async def test_create_omits_nullable_core_scale_201(
    authed_client: AsyncClient, field: str, day: str
) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["date"] = day
    del payload[field]
    resp = await authed_client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 201
    assert resp.json()[field] is None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_entry_201_shape(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["date"] == "2026-02-01"
    assert body["overall"] == 3
    assert body["schema_version"] == 4
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


async def test_create_entry_stool_completeness_round_trips(authed_client: AsyncClient) -> None:
    """stool_completeness must actually persist, not just validate -- same class
    of silent-drop bug as TreatmentService.create() dropping doses_per_day.
    """
    payload = dict(_VALID_PAYLOAD)
    payload["stool_completeness"] = "incomplete"

    resp = await authed_client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 201
    assert resp.json()["stool_completeness"] == "incomplete"

    get_resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert get_resp.json()["stool_completeness"] == "incomplete"


async def test_create_entry_stool_completeness_optional(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    assert resp.json()["stool_completeness"] is None


async def test_create_entry_invalid_stool_completeness_422(authed_client: AsyncClient) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["stool_completeness"] = "partial"
    resp = await authed_client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 422


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
    "Last logged at" label, insights' correlation-feature exclusion list --
    treats the field as edit-time metadata. A caller-supplied entry_time on PUT must be silently ignored
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


async def test_update_entry_stool_completeness_persists(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    resp = await authed_client.put(
        "/api/v1/entries/2026-02-01", json={"stool_completeness": "complete"}
    )
    assert resp.status_code == 200
    assert resp.json()["stool_completeness"] == "complete"


async def test_update_entry_invalid_stool_completeness_422(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    resp = await authed_client.put(
        "/api/v1/entries/2026-02-01", json={"stool_completeness": "partial"}
    )
    assert resp.status_code == 422


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


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


async def _create_entry_days_ago(client: AsyncClient, days_ago: int) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["date"] = (local_today() - datetime.timedelta(days=days_ago)).isoformat()
    resp = await client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 201


def _expected_week_days(*days_ago: int) -> list[bool]:
    """Mon..Sun flags for the current local week, from entry offsets in days."""
    today = local_today()
    monday = today - datetime.timedelta(days=today.weekday())
    dates = {today - datetime.timedelta(days=d) for d in days_ago}
    return [(monday + datetime.timedelta(days=i)) in dates for i in range(7)]


async def test_stats_empty_user_zeroes(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/entries/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_checkins": 0,
        "current_streak_days": 0,
        "week_days": [False] * 7,
        "week_today_index": local_today().weekday(),
    }


async def test_stats_streak_ending_today_stops_at_gap(authed_client: AsyncClient) -> None:
    # today + yesterday are consecutive; the 4-days-ago entry is past a gap and
    # counts toward the total but not the streak.
    for days_ago in (4, 1, 0):
        await _create_entry_days_ago(authed_client, days_ago)

    resp = await authed_client.get("/api/v1/entries/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_checkins": 3,
        "current_streak_days": 2,
        "week_days": _expected_week_days(4, 1, 0),
        "week_today_index": local_today().weekday(),
    }


async def test_stats_streak_ending_yesterday_still_counts(authed_client: AsyncClient) -> None:
    # Logged daily through yesterday but not yet today -- streak is not lost.
    for days_ago in (3, 2, 1):
        await _create_entry_days_ago(authed_client, days_ago)

    resp = await authed_client.get("/api/v1/entries/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_checkins": 3,
        "current_streak_days": 3,
        "week_days": _expected_week_days(3, 2, 1),
        "week_today_index": local_today().weekday(),
    }


async def test_stats_streak_zero_when_last_entry_two_days_ago(authed_client: AsyncClient) -> None:
    for days_ago in (3, 2):
        await _create_entry_days_ago(authed_client, days_ago)

    resp = await authed_client.get("/api/v1/entries/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_checkins": 2,
        "current_streak_days": 0,
        "week_days": _expected_week_days(3, 2),
        "week_today_index": local_today().weekday(),
    }


async def test_stats_week_days_shape_and_marked_positions(authed_client: AsyncClient) -> None:
    await _create_entry_days_ago(authed_client, 0)
    await _create_entry_days_ago(authed_client, 1)

    week_days = (await authed_client.get("/api/v1/entries/stats")).json()["week_days"]
    assert len(week_days) == 7
    assert all(isinstance(day, bool) for day in week_days)

    # Positions are Mon=0..Sun=6, so weekday() is the index directly. On a Monday
    # "yesterday" is last week's Sunday and must stay unmarked -- hence no
    # hardcoded indices here.
    today = local_today()
    expected = {today.weekday()}
    if today.weekday() != 0:
        expected.add((today - datetime.timedelta(days=1)).weekday())
    assert {i for i, marked in enumerate(week_days) if marked} == expected


async def test_stats_week_days_excludes_last_week(authed_client: AsyncClient) -> None:
    # Exactly 7 days back is the same weekday one week earlier -- always outside
    # the current week, whatever day the suite runs on.
    await _create_entry_days_ago(authed_client, 7)

    resp = await authed_client.get("/api/v1/entries/stats")
    assert resp.json()["total_checkins"] == 1
    assert resp.json()["week_days"] == [False] * 7


async def test_stats_route_declared_above_date_route(authed_client: AsyncClient) -> None:
    """Regression guard: /stats must be declared above /{date} in the router,
    or FastAPI 422s trying to parse "stats" as a date.
    """
    resp = await authed_client.get("/api/v1/entries/stats")
    assert resp.status_code != 422
    assert resp.status_code == 200
