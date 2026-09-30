from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, patch

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp import tools as t_mod
from app.models.entry import Entry
from app.models.tracker import Tracker

from tests.test_mcp_tools import _seed_entry, _seed_lab, _seed_treatment


def _tool_fn(server: FastMCP, name: str):
    return next(t for t in server._tool_manager.list_tools() if t.name == name).fn


def _mock_ro_session(async_db: AsyncSession):
    return patch(
        "app.mcp.tools.scoped_ro_session",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=async_db),
            __aexit__=AsyncMock(return_value=False),
        ),
    )


def _mock_main_session(async_db: AsyncSession):
    return patch(
        "app.mcp.tools.scoped_main_session",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=async_db),
            __aexit__=AsyncMock(return_value=False),
        ),
    )


def test_registered_tool_names() -> None:
    server = FastMCP("test")
    t_mod.register_tools(server)
    names = {t.name for t in server._tool_manager.list_tools()}
    assert names == {
        "delete_meal",
        "edit_meal",
        "get_day",
        "get_lab",
        "get_lab_history",
        "get_meal",
        "hypotheses",
        "list_days",
        "list_people",
        "list_supplements",
        "log_dose",
        "log_flare",
        "log_meal",
        "log_tracker",
        "save_day",
        "search",
        "set_ingredients",
        "set_supplements",
        "tag_meal",
        "treatments",
        "update_hypothesis",
    }


async def test_get_day_and_list_days(async_db: AsyncSession) -> None:
    await _seed_entry(async_db, "2025-03-10")
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        day = await _tool_fn(server, "get_day")(date="2025-03-10")
        listed = await _tool_fn(server, "list_days")(start_date="2025-03-01", end_date="2025-03-31")
    assert day is not None
    assert day["date"] == "2025-03-10"
    assert listed["days"][0]["date"] == "2025-03-10"


async def test_save_day_only_touches_target_date(async_db: AsyncSession) -> None:
    await _seed_entry(async_db, "2025-01-01")
    target = "2026-09-30"
    with _mock_main_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "save_day")(
            date=target,
            overall=6,
            notes="mcp isolation test",
        )
    assert result["date"] == target
    rows = (await async_db.execute(select(Entry.date))).scalars().all()
    assert datetime.date(2025, 1, 1) in rows
    assert datetime.date.fromisoformat(target) in rows
    assert len(rows) == 2


async def test_save_day_new_date_accepts_joint_pain_and_neuro(async_db: AsyncSession) -> None:
    """Regression: EntryCreate got duplicate joint_pain/neuro kwargs for a date with no row."""
    target = "2026-09-29"
    with _mock_main_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "save_day")(
            date=target, overall=4, joint_pain=3, neuro=2, notes="new day with pain scores"
        )
    assert result["date"] == target
    row = (
        await async_db.execute(
            select(Entry).where(Entry.date == datetime.date.fromisoformat(target))
        )
    ).scalar_one()
    assert (row.joint_pain, row.neuro, row.overall) == (3, 2, 4)
    assert row.supplements == "" and row.sick is False


async def test_save_day_new_date_defaults_joint_pain_and_neuro_to_zero(
    async_db: AsyncSession,
) -> None:
    target = "2026-09-28"
    with _mock_main_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        await _tool_fn(server, "save_day")(date=target, overall=6)
    row = (
        await async_db.execute(
            select(Entry).where(Entry.date == datetime.date.fromisoformat(target))
        )
    ).scalar_one()
    assert (row.joint_pain, row.neuro) == (0, 0)


async def test_log_flare_on_target_day(async_db: AsyncSession) -> None:
    target = "2026-09-30"
    with _mock_main_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        await _tool_fn(server, "save_day")(date=target, overall=5)
        flare = await _tool_fn(server, "log_flare")(
            date=target, key="vss", severity=8, time="14:30"
        )
    assert flare["symptoms_json"]["vss"] == 8
    assert flare["symptom_events"][-1]["key"] == "vss"


async def test_log_meal_and_get_meal(async_db: AsyncSession) -> None:
    target = "2026-09-30"
    with _mock_main_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        await _tool_fn(server, "save_day")(date=target, overall=5)
        logged = await _tool_fn(server, "log_meal")(
            date=target,
            name="MCP test oats",
            meal_time="12:30",
            ingredients=["oats", "banana"],
        )
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        meal = await _tool_fn(server, "get_meal")(photo_id=logged["photo_id"])
    assert meal is not None
    assert meal["name"] == "MCP test oats"
    assert len(meal["analysis"]["ingredients"]) == 2


async def test_labs_and_treatments_reads(async_db: AsyncSession) -> None:
    await _seed_lab(async_db)
    await _seed_treatment(async_db, active=True)
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        history = await _tool_fn(server, "get_lab_history")(marker_canonical_name="crp")
        protocol = await _tool_fn(server, "treatments")()
    assert history["history"]
    assert protocol["protocol"]["items"]


async def test_log_dose_and_log_tracker(async_db: AsyncSession) -> None:
    treatment = await _seed_treatment(async_db, active=True)
    treatment.doses_per_day = 2
    await async_db.flush()
    tracker = Tracker(
        name="MCP tracker",
        kind="counter",
        position=50,
        archived=False,
        is_seed=False,
    )
    async_db.add(tracker)
    await async_db.flush()
    target = "2026-09-30"
    with _mock_main_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        dose = await _tool_fn(server, "log_dose")(
            treatment_id=treatment.id, date=target, doses_taken=1
        )
        tracked = await _tool_fn(server, "log_tracker")(tracker_id=tracker.id, date=target, value=3)
    assert dose["doses_taken"] == 1
    assert tracked["value"] == 3


async def test_list_people_empty(async_db: AsyncSession) -> None:
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        people = await _tool_fn(server, "list_people")()
    assert people["accepted"] == []
