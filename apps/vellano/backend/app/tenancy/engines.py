from __future__ import annotations

from collections import OrderedDict

from f0rge_db.db_url import asyncpg_connect_args, resolve_database_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.tenancy.errors import TenantContext

POOL_SIZE = 2
MAX_OVERFLOW = 3
POOL_RECYCLE_SECONDS = 1800
LRU_CAP = 25


class TenantEngineCache:
    def __init__(self) -> None:
        self._makers: OrderedDict[str, tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = (
            OrderedDict()
        )

    async def get_sessionmaker(self, tenant: TenantContext) -> async_sessionmaker[AsyncSession]:
        key = str(tenant.id)
        pair = self._makers.get(key)
        if pair is not None:
            self._makers.move_to_end(key)
            return pair[1]
        kwargs: dict = {
            "echo": False,
            "pool_size": POOL_SIZE,
            "max_overflow": MAX_OVERFLOW,
            "pool_recycle": POOL_RECYCLE_SECONDS,
        }
        connect_args = asyncpg_connect_args(tenant.database_url)
        if connect_args:
            kwargs["connect_args"] = connect_args
        engine = create_async_engine(resolve_database_url(tenant.database_url), **kwargs)
        maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        self._makers[key] = (engine, maker)
        self._makers.move_to_end(key)
        while len(self._makers) > LRU_CAP:
            _old_key, (old_engine, _old_maker) = self._makers.popitem(last=False)
            await old_engine.dispose()
        return maker

    async def dispose_all(self) -> None:
        engines = [pair[0] for pair in self._makers.values()]
        self._makers.clear()
        for engine in engines:
            await engine.dispose()


engine_cache = TenantEngineCache()
