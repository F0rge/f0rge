"""MCP-logged meals must show up in the app's day view exactly like app-created meals.

Regressions from 2026-10-14:

* A photo-less meal logged with MCP ``log_meal`` was missing from the Today meal list and the
  diet-risk aggregation, because ``GET /api/v1/entries/{date}`` is served from the Redis entry
  cache and MCP writes never invalidated it.
* ``edit_meal(meal_time=<other day>)`` changed the time but left the meal on its old day,
  because day membership is ``Photo.entry_id`` and only ``meal_time`` was updated.

Real committed rows and real scoped MCP sessions, following tests/test_mcp_database.py; the app
side goes through the real FastAPI route with a session for the same user.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, AsyncIterator

import httpx
import pytest
import sqlalchemy as sa
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cache.keys import entry_key
from app.database import get_db
from app.main import app
from app.models.meal_tag import MealTag
from app.models.photo import Photo
from app.services.auth import create_access_token
from app.services.entries import get_or_create_entry
from f0rge_db.auth_context import user_id_ctx
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session
from tests.test_mcp_database import real_scoped_sessions  # noqa: F401
from tests.test_mcp_ingredients import _LEO, _call, _wipe, catalogue  # noqa: F401

_DAY = datetime.date(2031, 5, 6)  # wiped by test_mcp_ingredients._wipe
_PREV_DAY = datetime.date(2031, 5, 5)

pytestmark = pytest.mark.usefixtures("real_scoped_sessions", "catalogue")


app_client_maker: dict[str, Any] = {}


@pytest.fixture
async def app_client(async_engine, superuser_engine) -> AsyncIterator[httpx.AsyncClient]:
    """The real app as Leo, each request on its own committed session (sees MCP writes)."""
    maker = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _get_db() -> AsyncIterator[Any]:
        async with maker() as session:
            await apply_session_user_id(session, user_id_ctx.get() or _LEO)
            yield session

    app.dependency_overrides[get_db] = _get_db
    app_client_maker["maker"] = maker
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("ht_session", create_access_token(_LEO))
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        await _wipe_day(superuser_engine, _PREV_DAY)


async def _wipe_day(superuser_engine, day: datetime.date) -> None:
    photos = "SELECT p.id FROM photos p JOIN entries e ON e.id = p.entry_id WHERE e.date = :d"
    async with superuser_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "DELETE FROM photo_ingredients WHERE analysis_id IN "
                f"(SELECT id FROM photo_analyses WHERE photo_id IN ({photos}))"
            ),
            {"d": day},
        )
        await conn.execute(
            sa.text(f"DELETE FROM photo_analyses WHERE photo_id IN ({photos})"), {"d": day}
        )
        await conn.execute(
            sa.text("DELETE FROM photos WHERE entry_id IN (SELECT id FROM entries WHERE date=:d)"),
            {"d": day},
        )
        await conn.execute(sa.text("DELETE FROM entries WHERE date = :d"), {"d": day})


async def _app_day(client: httpx.AsyncClient, day: datetime.date) -> dict[str, Any] | None:
    resp = await client.get(f"/api/v1/entries/{day}")
    if resp.status_code == 404:
        return None
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _log(name: str, ingredients: list[str], day: datetime.date = _DAY, at: str = "13:00"):
    return await _call("log_meal", date=str(day), name=name, meal_time=at, ingredients=ingredients)


async def test_photo_less_mcp_meal_is_in_app_day_and_diet_risk(app_client) -> None:
    """Uncached: the app treats an MCP meal like an app meal (list, signal, Library tile)."""
    first = await _log("zz-Fusilli", ["wheat flour"], at="18:50")
    second = await _log("zz-leftover noodles", ["muesli", "raisin", "oats"])
    assert second["has_photo"] is False and second["matched_count"] == 3

    day = await _app_day(app_client, _DAY)
    assert day is not None
    photos = {p["id"]: p for p in day["photos"]}
    assert set(photos) == {first["photo_id"], second["photo_id"]}
    assert photos[second["photo_id"]]["has_image"] is False
    assert photos[second["photo_id"]]["derived_diet_tags"] == ["gluten", "high-fodmap"]
    signal = day["photo_signal"]
    assert set(signal["flags"]) == {"gluten", "high-fodmap"}
    assert signal["sources"]["gluten"] == ["wheat flour", "muesli"]
    assert signal["sources"]["high-fodmap"] == ["wheat flour", "raisin"]

    mcp_day = await _call("get_day", date=str(_DAY))
    assert sorted(m["photo_id"] for m in mcp_day["meals"]) == sorted(photos)


async def test_mcp_log_meal_invalidates_cached_app_day(app_client, memory_redis) -> None:
    """The prod bug: the app had cached the day before log_meal and kept serving it."""
    first = await _log("zz-Fusilli", ["wheat flour"], at="18:50")
    before = await _app_day(app_client, _DAY)
    assert [p["id"] for p in before["photos"]] == [first["photo_id"]]
    assert entry_key(_LEO, _DAY) in memory_redis["store"]

    second = await _log("zz-leftover noodles", ["muesli", "raisin"])

    after = await _app_day(app_client, _DAY)
    assert sorted(p["id"] for p in after["photos"]) == sorted(
        [first["photo_id"], second["photo_id"]]
    )
    assert after["photo_signal"]["sources"]["gluten"] == ["wheat flour", "muesli"]


async def test_mcp_set_ingredients_and_tag_meal_invalidate_cached_app_day(
    app_client, memory_redis
) -> None:
    logged = await _log("zz-plain oats", ["oats"])
    cached = await _app_day(app_client, _DAY)
    assert cached["photo_signal"]["flags"] == []

    await _call("set_ingredients", photo_id=logged["photo_id"], ingredients=["muesli"])
    assert (await _app_day(app_client, _DAY))["photo_signal"]["flags"] == ["gluten"]

    await _call("tag_meal", photo_id=logged["photo_id"], handles=[])
    assert entry_key(_LEO, _DAY) not in memory_redis["store"]


async def test_edit_meal_time_on_another_day_moves_the_meal(app_client, memory_redis) -> None:
    """edit_meal(meal_time on day D) re-homes the meal on D, creating D's entry if needed."""
    logged = await _log("zz-chicken noodles", ["muesli"], day=_PREV_DAY)
    assert (await _app_day(app_client, _DAY)) is None
    assert len((await _app_day(app_client, _PREV_DAY))["photos"]) == 1

    result = await _call("edit_meal", photo_id=logged["photo_id"], meal_time=f"{_DAY}T13:00:00")
    assert result["meal_time"] == f"{_DAY}T11:00:00+00:00"  # 13:00 CEST

    moved = await _app_day(app_client, _DAY)
    assert moved is not None, "target day must exist (created by edit_meal)"
    assert [p["id"] for p in moved["photos"]] == [logged["photo_id"]]
    assert moved["photo_signal"]["flags"] == ["gluten"]
    assert (await _app_day(app_client, _PREV_DAY))["photos"] == []

    meal = await _call("get_meal", photo_id=logged["photo_id"])
    assert meal["date"] == str(_DAY)
    assert (await _call("get_day", date=str(_PREV_DAY)))["meals"] == []
    assert result["date"] == str(_DAY)


async def test_edit_meal_same_day_time_change_keeps_day(app_client) -> None:
    logged = await _log("zz-lunch", ["oats"])
    result = await _call(
        "edit_meal", photo_id=logged["photo_id"], meal_time=f"{_DAY}T12:15:00+02:00"
    )
    assert result["meal_time"] == f"{_DAY}T10:15:00+00:00"
    assert [p["id"] for p in (await _app_day(app_client, _DAY))["photos"]] == [logged["photo_id"]]


# --------------------------------------------------------------------------- local time (Europe/Luxembourg)


async def test_log_meal_naive_times_are_luxembourg_local(app_client) -> None:
    hhmm = await _log("zz-lunch", ["oats"], at="13:00")
    assert hhmm["meal_time"] == f"{_DAY}T11:00:00+00:00"
    assert hhmm["meal_time_local"] == f"{_DAY}T13:00:00+02:00"

    naive_iso = await _log("zz-breakfast", ["oats"], at=f"{_DAY}T08:30:00")
    assert naive_iso["meal_time"] == f"{_DAY}T06:30:00+00:00"

    explicit = await _log("zz-late", ["oats"], at=f"{_DAY}T20:00:00+00:00")
    assert explicit["meal_time"] == f"{_DAY}T20:00:00+00:00"
    assert explicit["meal_time_local"] == f"{_DAY}T22:00:00+02:00"

    # The app reads stored meal_time as naive UTC, like its own uploads.
    day = await _app_day(app_client, _DAY)
    times = {p["id"]: p["meal_time"] for p in day["photos"]}
    assert times[hhmm["photo_id"]] == f"{_DAY}T11:00:00"
    assert times[naive_iso["photo_id"]] == f"{_DAY}T06:30:00"
    assert times[explicit["photo_id"]] == f"{_DAY}T20:00:00"


async def test_edit_meal_day_is_the_local_date(app_client) -> None:
    """23:30 UTC on the 5th is 01:30 on the 6th in Luxembourg: the meal stays on the 6th."""
    logged = await _log("zz-midnight snack", ["oats"])
    result = await _call(
        "edit_meal", photo_id=logged["photo_id"], meal_time=f"{_PREV_DAY}T23:30:00+00:00"
    )
    assert result["date"] == str(_DAY)
    assert result["meal_time_local"] == f"{_DAY}T01:30:00+02:00"
    assert [p["id"] for p in (await _app_day(app_client, _DAY))["photos"]] == [logged["photo_id"]]
    assert (await _app_day(app_client, _PREV_DAY)) is None

    # Naive input is local: 00:30 on the 5th local is stored as 22:30 UTC on the 4th.
    back = await _call("edit_meal", photo_id=logged["photo_id"], meal_time=f"{_PREV_DAY}T00:30:00")
    assert back["date"] == str(_PREV_DAY)
    assert back["meal_time"] == "2031-05-04T22:30:00+00:00"


# --------------------------------------------------------------------------- tagged copies


@pytest.fixture
async def tagged_meal(app_client, superuser_engine) -> AsyncIterator[dict[str, Any]]:
    """Leo's meal on _PREV_DAY with a delivered copy for Bea and a pending tag for Cleo."""
    bea, cleo = uuid.uuid4(), uuid.uuid4()
    async with superuser_engine.begin() as conn:
        for uid, name in ((bea, "bea"), (cleo, "cleo")):
            await conn.execute(
                sa.text(
                    "INSERT INTO users (id, email, password_hash, avatar_default_index, "
                    "created_at) VALUES (:id, :email, 'x', 0, now())"
                ),
                {"id": uid, "email": f"{name}-{uid}@example.com"},
            )
    logged = await _log("zz-shared noodles", ["muesli"], day=_PREV_DAY)
    maker = app_client_maker["maker"]
    async with maker() as s:
        await apply_session_user_id(s, bea)
        entry = await get_or_create_entry(s, _PREV_DAY)
        copy = Photo(
            user_id=bea,
            entry_id=entry.id,
            meal_id=logged["meal_id"],
            filename=None,
            label="zz-shared noodles",
            meal_time=datetime.datetime(2031, 5, 5, 11, 0),
            source_photo_id=logged["photo_id"],
            tagged_by_user_id=_LEO,
        )
        s.add(copy)
        await s.flush()
        copy_id = copy.id
        await s.commit()
        await apply_session_user_id(s, _LEO)
        for uid, status, delivered in (
            (bea, "delivered", copy_id),
            (cleo, "pending_approval", None),
        ):
            s.add(
                MealTag(
                    source_photo_id=logged["photo_id"],
                    source_meal_id=logged["meal_id"],
                    tagger_id=_LEO,
                    tagged_user_id=uid,
                    status=status,
                    source_label="zz-shared noodles",
                    source_date=_PREV_DAY,
                    delivered_photo_id=delivered,
                )
            )
        await s.commit()
        await clear_tenant_session(s)
    try:
        yield {"photo_id": logged["photo_id"], "copy_id": copy_id, "bea": bea, "cleo": cleo}
    finally:
        async with superuser_engine.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM meal_tags WHERE source_photo_id = :p"),
                {"p": logged["photo_id"]},
            )
            for uid in (bea, cleo):
                await conn.execute(sa.text("DELETE FROM photos WHERE user_id = :u"), {"u": uid})
                await conn.execute(sa.text("DELETE FROM entries WHERE user_id = :u"), {"u": uid})
                await conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": uid})


async def test_edit_meal_move_takes_tagged_copies_and_pending_tags(
    tagged_meal, superuser_engine, memory_redis
) -> None:
    bea = tagged_meal["bea"]
    memory_redis["store"][entry_key(bea, _PREV_DAY)] = "stale"
    memory_redis["store"][entry_key(bea, _DAY)] = "stale"

    result = await _call(
        "edit_meal", photo_id=tagged_meal["photo_id"], meal_time=f"{_DAY}T13:00:00"
    )
    assert result["date"] == str(_DAY)

    async with superuser_engine.connect() as conn:
        copy = (
            await conn.execute(
                sa.text(
                    "SELECT e.date, e.user_id, p.meal_time FROM photos p "
                    "JOIN entries e ON e.id = p.entry_id WHERE p.id = :id"
                ),
                {"id": tagged_meal["copy_id"]},
            )
        ).one()
        tags = dict(
            (
                await conn.execute(
                    sa.text(
                        "SELECT tagged_user_id, source_date FROM meal_tags "
                        "WHERE source_photo_id = :p"
                    ),
                    {"p": tagged_meal["photo_id"]},
                )
            ).all()
        )
    assert copy.date == _DAY and copy.user_id == bea  # Bea's own (new) entry for the 6th
    assert copy.meal_time == datetime.datetime(2031, 5, 6, 11, 0)
    assert tags == {bea: _DAY, tagged_meal["cleo"]: _DAY}
    assert entry_key(bea, _PREV_DAY) not in memory_redis["store"]
    assert entry_key(bea, _DAY) not in memory_redis["store"]
    assert result["moved_tag_copies"] == 1
