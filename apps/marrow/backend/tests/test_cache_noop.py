from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.supplement_catalog import SupplementCatalogService


@pytest.mark.usefixtures("memory_redis")
async def test_catalog_cache_round_trip(async_db: AsyncSession, memory_redis: dict) -> None:
    service = SupplementCatalogService(async_db)
    first = await service.list_items()
    second = await service.list_items()
    assert memory_redis["metrics"]["set"] == 1
    assert memory_redis["metrics"]["get"] == 2
    assert len(first) == len(second)


async def test_redis_helpers_noop_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "redis_url", "")
    from app.cache import redis_client

    await redis_client.set("k", "v", 60)
    assert await redis_client.get("k") is None
    await redis_client.delete("k")
    assert await redis_client.delete_pattern("u:*") == 0
