"""Composition module: Vellano engine/session from f0rge_db factories.

S0 has no domain tables yet. Later slices import ``Base`` and ``get_db`` here.
Never point this at Marrow ``DATABASE_URL``.
"""

from __future__ import annotations

from f0rge_db.engine import build_get_db, create_engine_and_sessionmaker, register_rls_hook
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine, async_session_maker = create_engine_and_sessionmaker(
    settings.database_url,
    direct_database_url=settings.direct_database_url,
)

register_rls_hook()


class Base(DeclarativeBase):
    pass


get_db = build_get_db(async_session_maker)
