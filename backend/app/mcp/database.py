from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.db_url import asyncpg_connect_args, resolve_database_url

_ro_engine: Optional[AsyncEngine] = None
_main_engine: Optional[AsyncEngine] = None


def get_ro_engine() -> AsyncEngine:
    """Lazily create the read-only engine pointing at the healthtracker_ro role.

    Uses mcp_readonly_database_url from config; falls back to the main database_url
    when not set (e.g. in tests where the ro role may not exist). A statement_timeout
    is set on every connection because read_sql accepts arbitrary client-supplied
    SELECT text — the timeout keeps a pathological query from pinning a connection.
    """
    global _ro_engine
    if _ro_engine is None:
        url = resolve_database_url(
            settings.mcp_readonly_database_url or settings.database_url,
            direct_url=settings.direct_database_url,
        )
        connect_args = asyncpg_connect_args(
            settings.mcp_readonly_database_url or settings.database_url
        )
        kwargs: dict = {
            "pool_pre_ping": True,
            "connect_args": {
                "server_settings": {"statement_timeout": "10000"},
                **connect_args,
            },
        }
        _ro_engine = create_async_engine(url, **kwargs)
    return _ro_engine


def get_main_engine() -> AsyncEngine:
    """Lazily create the main engine for reading user_settings (token validation, etc.)."""
    global _main_engine
    if _main_engine is None:
        url = resolve_database_url(
            settings.database_url,
            direct_url=settings.direct_database_url,
        )
        kwargs: dict = {"pool_pre_ping": True}
        connect_args = asyncpg_connect_args(settings.database_url)
        if connect_args:
            kwargs["connect_args"] = connect_args
        _main_engine = create_async_engine(url, **kwargs)
    return _main_engine


def make_ro_session() -> AsyncSession:
    maker = async_sessionmaker(get_ro_engine(), expire_on_commit=False)
    return maker()


def make_main_session() -> AsyncSession:
    maker = async_sessionmaker(get_main_engine(), expire_on_commit=False)
    return maker()
