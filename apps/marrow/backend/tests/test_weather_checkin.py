"""Check-in attaches one Open-Meteo reading for the current user."""

from __future__ import annotations

import datetime
from typing import Optional

import pytest
from httpx import AsyncClient

from app.services.open_meteo import OpenMeteoDay
from app.utils.dates import local_today

_ENTRY_PAYLOAD = {
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

_FAKE_DAY = OpenMeteoDay(
    temp_mean=12.4,
    temp_min=8.0,
    temp_max=16.0,
    humidity_mean=71.2,
    pressure_mean=1014.6,
    weather_main="Clouds",
)


def _patch_meteo(
    monkeypatch: pytest.MonkeyPatch, day: Optional[OpenMeteoDay] = _FAKE_DAY
) -> list[datetime.date]:
    calls: list[datetime.date] = []

    async def _fake(target: datetime.date) -> Optional[OpenMeteoDay]:
        calls.append(target)
        return day

    monkeypatch.setattr("app.services.weather.fetch_open_meteo_day", _fake)
    return calls


async def test_create_entry_stores_weather_for_current_user(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    day = datetime.date(2026, 3, 10)
    calls = _patch_meteo(monkeypatch)
    resp = await authed_client.post(
        "/api/v1/entries", json={**_ENTRY_PAYLOAD, "date": day.isoformat()}
    )
    assert resp.status_code == 201
    assert calls == [day]

    weather = await authed_client.get(f"/api/v1/weather/{day.isoformat()}")
    assert weather.status_code == 200
    body = weather.json()
    assert body["temp_mean"] == 12.4
    assert body["humidity_mean"] == 71.2
    assert body["pressure_mean"] == 1014.6
    assert body["reading_count"] == 1


async def test_second_save_same_day_does_not_refetch(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    day = datetime.date(2026, 3, 11)
    calls = _patch_meteo(monkeypatch)
    created = await authed_client.post(
        "/api/v1/entries", json={**_ENTRY_PAYLOAD, "date": day.isoformat()}
    )
    assert created.status_code == 201
    updated = await authed_client.put(f"/api/v1/entries/{day.isoformat()}", json={"overall": 4})
    assert updated.status_code == 200
    assert calls == [day]


async def test_weather_failure_does_not_fail_entry(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    day = datetime.date(2026, 3, 12)

    async def _boom(_target: datetime.date) -> None:
        raise RuntimeError("Open-Meteo down")

    monkeypatch.setattr("app.services.weather.fetch_open_meteo_day", _boom)
    resp = await authed_client.post(
        "/api/v1/entries", json={**_ENTRY_PAYLOAD, "date": day.isoformat()}
    )
    assert resp.status_code == 201
    weather = await authed_client.get(f"/api/v1/weather/{day.isoformat()}")
    assert weather.status_code == 404


async def test_fetch_now_stores_today_for_current_user(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_meteo(monkeypatch)
    resp = await authed_client.post("/api/v1/weather/fetch")
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == local_today().isoformat()
    assert body["temperature_c"] == 12.4
    assert body["weather_main"] == "Clouds"
    assert calls == [local_today()]


async def test_fetch_now_failure_is_502(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_meteo(monkeypatch, day=None)
    resp = await authed_client.post("/api/v1/weather/fetch")
    assert resp.status_code == 502


@pytest.mark.usefixtures("memory_redis")
async def test_checkin_populates_feature_matrix_wx(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    day = datetime.date(2026, 3, 13)
    _patch_meteo(monkeypatch)
    created = await authed_client.post(
        "/api/v1/entries", json={**_ENTRY_PAYLOAD, "date": day.isoformat()}
    )
    assert created.status_code == 201

    matrix = await authed_client.get(
        "/api/v1/analytics/feature-matrix",
        params={"start": day.isoformat(), "end": day.isoformat(), "size": 5},
    )
    assert matrix.status_code == 200
    row = matrix.json()["data"][0]
    assert row["wx_temp_mean"] == 12.4
    assert row["wx_humidity_mean"] == 71.2
    assert row["wx_pressure_mean"] == 1014.6
    assert row["wx_condition"] == "Clouds"
