from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.cache.keys import catalog_key, feature_matrix_prefix, signals_prefix
from tests.conftest import authed_user_id


@pytest.mark.usefixtures("memory_redis")
async def test_warm_populates_catalog_keys(
    authed_client: AsyncClient,
    memory_redis: dict,
) -> None:
    user_id = await authed_user_id(authed_client)
    resp = await authed_client.post("/api/v1/cache/warm")
    assert resp.status_code == 204

    store = memory_redis["store"]
    for kind in ("supplements", "medications", "diet_tags", "symptoms", "trackers"):
        key = catalog_key(uuid.UUID(str(user_id)), kind, False)
        assert key in store, f"missing warmed catalog key {key}"


@pytest.mark.usefixtures("memory_redis")
async def test_warm_does_not_populate_feature_matrix_or_signals_keys(
    authed_client: AsyncClient,
    memory_redis: dict,
) -> None:
    user_id = uuid.UUID(str(await authed_user_id(authed_client)))
    resp = await authed_client.post("/api/v1/cache/warm")
    assert resp.status_code == 204

    store = memory_redis["store"]
    fm_prefix = feature_matrix_prefix(user_id)
    signals_pfx = signals_prefix(user_id)
    for key in store:
        assert not key.startswith(fm_prefix), f"unexpected feature-matrix key {key}"
        assert not key.startswith(signals_pfx), f"unexpected signals key {key}"
