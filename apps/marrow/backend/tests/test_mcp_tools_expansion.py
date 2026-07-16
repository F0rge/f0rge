from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp import tools as t_mod
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.models.tracker import Tracker
from app.models.tracker_log import TrackerLog
from app.models.weather import WeatherReading

from tests.test_mcp_tools import _seed_entry, _seed_lab


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


async def _seed_photo_analysis(
    db: AsyncSession,
    *,
    date_str: str = "2025-01-15",
    dish_name: str = "Pasta",
) -> tuple[Entry, Photo, PhotoAnalysis, PhotoIngredient]:
    entry = await _seed_entry(db, date_str)
    photo = Photo(
        entry_id=entry.id,
        filename=f"{date_str}_meal.jpg",
        label="Dinner",
        meal_time=datetime.datetime(2025, 1, 15, 19, 30),
    )
    db.add(photo)
    await db.flush()
    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name=dish_name,
        cuisine="Italian",
        dish_confidence=0.85,
        gluten_free_confirmed=True,
        lactose_free_confirmed=False,
    )
    db.add(analysis)
    await db.flush()
    ingredient = PhotoIngredient(
        analysis_id=analysis.id,
        name="Wheat pasta",
        canonical_name="pasta",
        visible=True,
        confidence=0.9,
        user_edited=False,
        histamine_score=1,
        fodmap_oligos="low",
        fodmap_fructose=None,
        fodmap_polyols=None,
        fodmap_lactose="low",
        contains_gluten=True,
        contains_dairy=False,
    )
    db.add(ingredient)
    await db.flush()
    return entry, photo, analysis, ingredient


async def _seed_tracker_log(db: AsyncSession) -> tuple[Tracker, TrackerLog]:
    tracker = Tracker(
        name="Mood",
        kind="binary",
        icon="smile",
        position=10,
        archived=False,
        is_seed=False,
    )
    db.add(tracker)
    await db.flush()
    log = TrackerLog(
        tracker_id=tracker.id,
        date=datetime.date(2025, 1, 15),
        value=1,
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(log)
    await db.flush()
    return tracker, log


async def test_get_photo_analysis_returns_ingredients_with_diet_fields(
    async_db: AsyncSession,
) -> None:
    _, photo, _, ingredient = await _seed_photo_analysis(async_db)

    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_photo_analysis")(photo_id=photo.id)

    assert result is not None
    assert result["dish_name"] == "Pasta"
    assert result["status"] == "confirmed"
    assert result["gluten_free_confirmed"] is True
    assert result["lactose_free_confirmed"] is False
    assert len(result["ingredients"]) == 1
    ing = result["ingredients"][0]
    assert ing["id"] == ingredient.id
    assert ing["canonical_name"] == "pasta"
    assert ing["histamine_score"] == 1
    assert ing["fodmap_lactose"] == "low"
    assert ing["contains_gluten"] is True
    assert ing["contains_dairy"] is False


async def test_get_photo_analysis_missing_returns_none(async_db: AsyncSession) -> None:
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_photo_analysis")(photo_id=999999)

    assert result is None


async def test_list_photos_for_entry_by_date(async_db: AsyncSession) -> None:
    _, photo, analysis, _ = await _seed_photo_analysis(async_db)

    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "list_photos_for_entry")(date="2025-01-15")

    assert result["date"] == "2025-01-15"
    assert len(result["photos"]) == 1
    row = result["photos"][0]
    assert row["id"] == photo.id
    assert row["label"] == "Dinner"
    assert row["meal_time"] == "2025-01-15T19:30:00"
    assert row["analysis_status"] == analysis.status


async def test_list_trackers_active_only(async_db: AsyncSession) -> None:
    async_db.add(
        Tracker(
            name="Active custom",
            kind="binary",
            position=5,
            archived=False,
            is_seed=False,
        )
    )
    async_db.add(
        Tracker(
            name="Archived custom",
            kind="binary",
            position=6,
            archived=True,
            is_seed=False,
        )
    )
    await async_db.flush()

    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "list_trackers")(active_only=True)

    names = [t["name"] for t in result["trackers"]]
    assert "Active custom" in names
    assert "Archived custom" not in names


async def test_get_tracker_logs_in_range(async_db: AsyncSession) -> None:
    tracker, log = await _seed_tracker_log(async_db)

    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_tracker_logs")(
            tracker_id=tracker.id,
            start_date="2025-01-01",
            end_date="2025-01-31",
        )

    assert result["tracker_id"] == tracker.id
    assert len(result["logs"]) == 1
    assert result["logs"][0]["date"] == str(log.date)
    assert result["logs"][0]["value"] == 1


async def test_get_tracker_logs_empty_for_unknown_tracker(async_db: AsyncSession) -> None:
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_tracker_logs")(
            tracker_id=999999,
            start_date="2025-01-01",
            end_date="2025-01-31",
        )

    assert result["logs"] == []


async def test_list_health_metrics_range(async_db: AsyncSession) -> None:
    async_db.add(
        HealthMetric(
            date=datetime.date(2025, 1, 15),
            sleep_hours=7.5,
            steps=8000,
            source="health_auto_export",
        )
    )
    async_db.add(
        HealthMetric(
            date=datetime.date(2025, 1, 16),
            hrv_mean=45.0,
            source="health_auto_export",
        )
    )
    await async_db.flush()

    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        all_metrics = await _tool_fn(server, "list_health_metrics")(
            start_date="2025-01-01",
            end_date="2025-01-31",
        )
        sleep_metrics = await _tool_fn(server, "list_health_metrics")(
            start_date="2025-01-01",
            end_date="2025-01-31",
            metric_type="sleep",
        )

    assert len(all_metrics["metrics"]) == 2
    assert len(sleep_metrics["metrics"]) == 1
    assert sleep_metrics["metrics"][0]["sleep_hours"] == pytest.approx(7.5)


async def test_list_health_metrics_invalid_metric_type(async_db: AsyncSession) -> None:
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        tool_fn = _tool_fn(server, "list_health_metrics")
        with pytest.raises(ValueError, match="metric_type"):
            await tool_fn(
                start_date="2025-01-01",
                end_date="2025-01-31",
                metric_type="invalid",
            )


async def test_get_weather_for_entry(async_db: AsyncSession) -> None:
    day = datetime.date(2025, 1, 15)
    async_db.add(
        WeatherReading(
            timestamp=datetime.datetime(2025, 1, 15, 12, 0),
            date=day,
            temperature_c=10.0,
            humidity_pct=60.0,
            pressure_hpa=1013.0,
            weather_main="Clouds",
        )
    )
    await async_db.flush()

    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_weather_for_entry")(date="2025-01-15")

    assert result is not None
    assert result["date"] == "2025-01-15"
    assert result["temp_mean"] == pytest.approx(10.0)
    assert result["reading_count"] == 1


async def test_get_weather_for_entry_missing_returns_none(async_db: AsyncSession) -> None:
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_weather_for_entry")(date="2099-01-01")

    assert result is None


async def test_get_lab_markers(async_db: AsyncSession) -> None:
    lab, _, marker = await _seed_lab(async_db)

    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_lab_markers")(lab_id=lab.id)

    assert result is not None
    assert result["lab_id"] == lab.id
    assert len(result["markers"]) == 1
    assert result["markers"][0]["canonical_name"] == marker.canonical_name
    assert result["markers"][0]["value"] == pytest.approx(marker.value)


async def test_get_lab_markers_missing_returns_none(async_db: AsyncSession) -> None:
    with _mock_ro_session(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool_fn(server, "get_lab_markers")(lab_id=999999)

    assert result is None
