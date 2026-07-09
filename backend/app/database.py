from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.auth_context import user_id_ctx
from app.config import settings
from app.db_url import asyncpg_connect_args, resolve_database_url
from app.tenant import apply_session_user_id

_db_url = resolve_database_url(
    settings.database_url,
    direct_url=settings.direct_database_url,
)
_engine_kwargs = {"echo": False}
_connect_args = asyncpg_connect_args(settings.database_url)
if _connect_args:
    _engine_kwargs["connect_args"] = _connect_args

engine: AsyncEngine = create_async_engine(_db_url, **_engine_kwargs)

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        user_id = user_id_ctx.get()
        if user_id is not None:
            await apply_session_user_id(session, user_id)
        yield session
