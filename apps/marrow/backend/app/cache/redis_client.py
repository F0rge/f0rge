from __future__ import annotations

import json
import logging
from typing import Any, Optional

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[Redis] = None


def _redis_enabled() -> bool:
    return bool(settings.redis_url)


async def _get_client() -> Optional[Redis]:
    global _client
    if not _redis_enabled():
        return None
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def get(key: str) -> Optional[str]:
    client = await _get_client()
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception:
        logger.exception("Redis GET failed for key %s", key)
        return None


async def set(key: str, value: str, ttl_seconds: int) -> None:
    client = await _get_client()
    if client is None:
        return
    try:
        await client.set(key, value, ex=ttl_seconds)
    except Exception:
        logger.exception("Redis SET failed for key %s", key)


async def delete(key: str) -> None:
    client = await _get_client()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception:
        logger.exception("Redis DELETE failed for key %s", key)


async def delete_pattern(pattern: str) -> int:
    client = await _get_client()
    if client is None:
        return 0
    deleted = 0
    try:
        async for key in client.scan_iter(match=pattern, count=100):
            await client.delete(key)
            deleted += 1
    except Exception:
        logger.exception("Redis DELETE pattern failed for %s", pattern)
    return deleted


def dumps_json(value: Any) -> str:
    return json.dumps(value, default=str)


def loads_json(value: str) -> Any:
    return json.loads(value)


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
