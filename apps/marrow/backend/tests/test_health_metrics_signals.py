"""Manual health import lands in the feature matrix and Signals."""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient

from app.services.signals.effects import MIN_OBSERVED_DAYS
from app.utils.dates import local_today

SAMPLES_URL = "/api/v1/health-metrics/samples"

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


async def _create_entry_on_date(client: AsyncClient, date: datetime.date, **extra: object) -> None:
    payload = dict(_ENTRY_PAYLOAD)
    payload["date"] = date.isoformat()
    payload.update(extra)
    resp = await client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 201


def _fast_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.signals.service.estimate_all_effects",
        lambda rows, columns, baseline, **kwargs: __import__(
            "app.services.signals.effects", fromlist=["estimate_all_effects"]
        ).estimate_all_effects(
            rows,
            columns,
            baseline,
            bootstrap_n=50,
            rng=kwargs.get("rng"),
        ),
    )


@pytest.mark.usefixtures("memory_redis")
async def test_manual_import_populates_feature_matrix_and_signals(
    authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fast_effects(monkeypatch)
    today = local_today()
    samples: list[dict[str, object]] = []
    for offset in range(62):
        day = today - datetime.timedelta(days=offset)
        sleep = 5.0 + float(offset % 5)
        overall = 1 if sleep <= 6 else (5 if sleep >= 8 else 3)
        await _create_entry_on_date(authed_client, day, overall=overall)
        samples.append(
            {
                "date": day.isoformat(),
                "sleep_hours": sleep,
                "hrv_mean": 40.0 + float(offset % 10),
                "resting_hr": 58.0 + float(offset % 6),
                "steps": 4000 + offset * 50,
                "source": "manual_import",
            }
        )

    imported = await authed_client.post(SAMPLES_URL, json={"samples": samples})
    assert imported.status_code == 200
    assert imported.json()["dates_upserted"] == 62

    matrix = await authed_client.get(
        "/api/v1/analytics/feature-matrix",
        params={"start": samples[-1]["date"], "end": today.isoformat(), "size": 90},
    )
    assert matrix.status_code == 200
    rows = matrix.json()["data"]
    assert rows
    hm_sleep = [row["hm_sleep_hours"] for row in rows if row.get("hm_sleep_hours") is not None]
    assert len(hm_sleep) == 62
    assert 5.0 in hm_sleep
    assert 9.0 in hm_sleep

    signals = await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert signals.status_code == 200
    body = signals.json()
    assert body["meta"]["insufficient_data"] is False
    assert body["meta"]["days_usable"] >= MIN_OBSERVED_DAYS
    features = {driver["feature"] for driver in body["drivers"]}
    assert "hm_sleep_hours" in features


@pytest.mark.usefixtures("memory_redis")
async def test_ingest_refreshes_cached_feature_matrix(authed_client: AsyncClient) -> None:
    today = local_today()
    await _create_entry_on_date(authed_client, today)
    params = {"start": today.isoformat(), "end": today.isoformat(), "size": 5}

    stale = await authed_client.get("/api/v1/analytics/feature-matrix", params=params)
    assert stale.status_code == 200
    assert stale.json()["data"][0]["hm_sleep_hours"] is None

    posted = await authed_client.post(
        SAMPLES_URL,
        json={
            "samples": [{"date": today.isoformat(), "sleep_hours": 7.5, "source": "manual_import"}]
        },
    )
    assert posted.status_code == 200

    fresh = await authed_client.get("/api/v1/analytics/feature-matrix", params=params)
    assert fresh.status_code == 200
    assert fresh.json()["data"][0]["hm_sleep_hours"] == 7.5
