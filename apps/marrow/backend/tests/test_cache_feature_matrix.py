from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.feature_matrix import build_feature_matrix

_DATE = datetime.date(2026, 3, 1)


@pytest.mark.usefixtures("memory_redis")
async def test_feature_matrix_cache_hit(async_db: AsyncSession, memory_redis: dict) -> None:
    start = _DATE
    end = _DATE + datetime.timedelta(days=2)

    rows1, cols1 = await build_feature_matrix(async_db, start, end)
    assert memory_redis["metrics"]["set"] == 1

    rows2, cols2 = await build_feature_matrix(async_db, start, end)
    assert memory_redis["metrics"]["set"] == 1
    assert memory_redis["metrics"]["get"] == 2
    assert rows1 == rows2
    assert cols1 == cols2


async def test_feature_matrix_noop_without_redis(
    async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "redis_url", "")
    start = _DATE
    end = _DATE

    rows1, _ = await build_feature_matrix(async_db, start, end)
    rows2, _ = await build_feature_matrix(async_db, start, end)
    assert rows1 == rows2
