from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.cache.keys import catalog_key
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
