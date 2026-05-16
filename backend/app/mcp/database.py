from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

_ro_engine: AsyncEngine | None = None
_main_engine: AsyncEngine | None = None


def get_ro_engine() -> AsyncEngine:
    """Lazily create the read-only engine pointing at the healthtracker_ro role.

    Uses mcp_readonly_database_url from config; falls back to the main database_url
    when not set (e.g. in tests where the ro role may not exist).
    """
    global _ro_engine
    if _ro_engine is None:
        url = settings.mcp_readonly_database_url or settings.database_url
        _ro_engine = create_async_engine(url, pool_pre_ping=True)
    return _ro_engine


def get_main_engine() -> AsyncEngine:
    """Lazily create the main engine for reading user_settings (token validation, etc.)."""
    global _main_engine
    if _main_engine is None:
        _main_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _main_engine


def make_ro_session() -> AsyncSession:
    maker = async_sessionmaker(get_ro_engine(), expire_on_commit=False)
    return maker()


def make_main_session() -> AsyncSession:
    maker = async_sessionmaker(get_main_engine(), expire_on_commit=False)
    return maker()
