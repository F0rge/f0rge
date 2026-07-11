"""Composition module: builds marrow's engine/session from f0rge_db factories.

Keeps the historical public surface — ``engine``, ``async_session_maker``,
``Base``, ``get_db`` — so ``from app.database import ...`` works unchanged
across the app, tests, scripts, and migrations.
"""

from __future__ import annotations

from f0rge_db.engine import build_get_db, create_engine_and_sessionmaker, register_rls_hook
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine, async_session_maker = create_engine_and_sessionmaker(
    settings.database_url,
    direct_database_url=settings.direct_database_url,
)

# Re-apply app.user_id on every transaction begin (process-wide Session hook),
# same semantics as the module-level @event.listens_for this replaces.
register_rls_hook()


class Base(DeclarativeBase):
    pass


get_db = build_get_db(async_session_maker)
