from __future__ import annotations

from typing import AsyncIterator

from f0rge_db.engine import build_get_db, create_engine_and_sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import settings

_engine_cache: dict[tuple[str, str], tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = {}


class PlatformDatabaseUnconfiguredError(RuntimeError):
    """PLATFORM_DATABASE_URL is empty. Raised at first use, never at import."""


def platform_sessionmaker() -> async_sessionmaker[AsyncSession]:
    url = settings.platform_database_url
    if not url:
        raise PlatformDatabaseUnconfiguredError("PLATFORM_DATABASE_URL is not set")
    key = (url, settings.platform_direct_database_url)
    pair = _engine_cache.get(key)
    if pair is None:
        pair = create_engine_and_sessionmaker(url, direct_database_url=key[1])
        _engine_cache[key] = pair
    return pair[1]


async def get_platform_db() -> AsyncIterator[AsyncSession]:
    get_db = build_get_db(platform_sessionmaker())
    async for session in get_db():
        yield session


async def dispose_platform_engines() -> None:
    engines = [pair[0] for pair in _engine_cache.values()]
    _engine_cache.clear()
    for engine in engines:
        await engine.dispose()
