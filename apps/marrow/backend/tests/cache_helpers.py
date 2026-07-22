from __future__ import annotations

from typing import Any

import pytest

from app.config import settings


@pytest.fixture
def memory_redis(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """In-memory Redis stand-in; patches app.cache.redis_client helpers."""
    store: dict[str, str] = {}
    metrics = {"get": 0, "set": 0}

    async def fake_get(key: str) -> str | None:
        metrics["get"] += 1
        return store.get(key)

    async def fake_set(key: str, value: str, ttl_seconds: int) -> None:
        metrics["set"] += 1
        store[key] = value

    async def fake_delete(key: str) -> None:
        store.pop(key, None)

    async def fake_delete_pattern(pattern: str) -> int:
        prefix = pattern[:-1] if pattern.endswith("*") else pattern
        keys = [k for k in list(store) if k.startswith(prefix)]
        for key in keys:
            del store[key]
        return len(keys)

    monkeypatch.setattr(settings, "redis_url", "redis://memory/0")
    monkeypatch.setattr("app.cache.redis_client._client", None)
    monkeypatch.setattr("app.cache.redis_client.get", fake_get)
    monkeypatch.setattr("app.cache.redis_client.set", fake_set)
    monkeypatch.setattr("app.cache.redis_client.delete", fake_delete)
    monkeypatch.setattr("app.cache.redis_client.delete_pattern", fake_delete_pattern)

    return {"store": store, "metrics": metrics}
