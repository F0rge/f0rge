"""HTTP-level tests for GET /api/v1/signals."""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient

from app.cache.invalidation import invalidate_user_insights_cache
from app.cache.keys import signals_key
from app.services.signals.baseline import WARMUP_DAYS
from app.services.signals.service import SIGNALS_SCHEMA_VERSION
from app.utils.dates import local_today
from tests.conftest import authed_user_id

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

_MIRROR_FEATURES = frozenset(
    {
        "bloating",
        "joint_pain",
        "neuro",
        "stress",
        "sleep_quality",
    }
)


async def _create_entry_on_date(client: AsyncClient, date: datetime.date, **extra: object) -> None:
    payload = dict(_ENTRY_PAYLOAD)
    payload["date"] = date.isoformat()
    payload.update(extra)
    resp = await client.post("/api/v1/entries", json=payload)
    assert resp.status_code == 201


async def _seed_usable_window(client: AsyncClient, days: int = 62) -> None:
    today = local_today()
    for offset in range(days):
        await _create_entry_on_date(client, today - datetime.timedelta(days=offset))


async def test_signals_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert resp.status_code == 401


async def test_signals_unknown_outcome_400(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/signals", params={"outcome": "not_a_real_outcome"})
    assert resp.status_code == 400
    assert "unknown outcome" in resp.json()["detail"].lower()


@pytest.mark.parametrize("bootstrap_n", [50])
async def test_signals_authenticated_returns_blocks(
    authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    bootstrap_n: int,
) -> None:
    monkeypatch.setattr(
        "app.services.signals.service.estimate_all_effects",
        lambda rows, columns, baseline, **kwargs: __import__(
            "app.services.signals.effects", fromlist=["estimate_all_effects"]
        ).estimate_all_effects(
            rows,
            columns,
            baseline,
            bootstrap_n=bootstrap_n,
            rng=kwargs.get("rng"),
        ),
    )
    await _seed_usable_window(authed_client, days=62)
    resp = await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert resp.status_code == 200
    body = resp.json()
    for key in ("meta", "model", "today", "drivers", "mirrors", "unexplained", "trends"):
        assert key in body
    assert body["meta"]["outcome"] == "overall"
    assert body["meta"]["insufficient_data"] is False
    assert isinstance(body["trends"]["series"], list)


async def test_signals_insufficient_data_returns_200_with_flag(authed_client: AsyncClient) -> None:
    await _seed_usable_window(authed_client, days=10)
    resp = await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["insufficient_data"] is True
    assert body["meta"]["days_usable"] < 30
    assert WARMUP_DAYS == body["meta"]["warmup"]
    assert body["meta"]["insufficient_reason"]
    assert body["drivers"] == []


async def test_signals_cache_hit_skips_recompute(
    authed_client: AsyncClient,
    memory_redis: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_usable_window(authed_client, days=62)
    calls = {"n": 0}
    real = __import__(
        "app.services.signals.effects", fromlist=["estimate_all_effects"]
    ).estimate_all_effects

    def counting_estimate(*args, **kwargs):
        calls["n"] += 1
        return real(*args, bootstrap_n=50, **kwargs)

    monkeypatch.setattr("app.services.signals.service.estimate_all_effects", counting_estimate)

    resp1 = await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    resp2 = await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert calls["n"] == 1


async def test_signals_invalidate_clears_cache(
    authed_client: AsyncClient,
    memory_redis: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_usable_window(authed_client, days=62)
    calls = {"n": 0}
    real = __import__(
        "app.services.signals.effects", fromlist=["estimate_all_effects"]
    ).estimate_all_effects

    def counting_estimate(*args, **kwargs):
        calls["n"] += 1
        return real(*args, bootstrap_n=50, **kwargs)

    monkeypatch.setattr("app.services.signals.service.estimate_all_effects", counting_estimate)

    await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    user_id = await authed_user_id(authed_client)
    today = local_today()
    await invalidate_user_insights_cache(user_id, today)
    await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert calls["n"] == 2


async def test_signals_no_mirrors_in_drivers_with_symptoms(
    authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.signals.service.estimate_all_effects",
        lambda rows, columns, baseline, **kwargs: __import__(
            "app.services.signals.effects", fromlist=["estimate_all_effects"]
        ).estimate_all_effects(rows, columns, baseline, bootstrap_n=50),
    )
    sym_resp = await authed_client.post(
        "/api/v1/symptoms/catalog",
        json={"key": "vss", "label": "Visual Snow"},
    )
    assert sym_resp.status_code in (200, 201)
    today = local_today()
    for offset in range(62):
        extra = {"symptoms_json": {"vss": (offset % 5) + 1}} if offset % 2 == 0 else {}
        await _create_entry_on_date(authed_client, today - datetime.timedelta(days=offset), **extra)

    resp = await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mirrors"]
    for driver in body["drivers"]:
        feature = driver["feature"]
        assert not feature.startswith("sym_")
        assert feature not in _MIRROR_FEATURES
    mirror_features = {m["feature"] for m in body["mirrors"]}
    assert any(f.startswith("sym_") for f in mirror_features)


async def test_signals_good_direction_on_drivers_and_trends(
    authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.signals.service.estimate_all_effects",
        lambda rows, columns, baseline, **kwargs: __import__(
            "app.services.signals.effects", fromlist=["estimate_all_effects"]
        ).estimate_all_effects(rows, columns, baseline, bootstrap_n=50),
    )
    await _seed_usable_window(authed_client, days=62)
    resp = await authed_client.get("/api/v1/signals", params={"outcome": "overall"})
    assert resp.status_code == 200
    body = resp.json()
    for driver in body["drivers"]:
        assert "good_direction" in driver
    for series in body["trends"]["series"]:
        assert "good_direction" in series
        if series["key"] == "overall":
            assert series["good_direction"] == "up"
        if series["key"] == "stress":
            assert series["good_direction"] == "down"


def test_signals_key_includes_schema_version() -> None:
    import uuid

    key = signals_key(uuid.uuid4(), "overall", None, None)
    assert f":v{SIGNALS_SCHEMA_VERSION}:" in key
