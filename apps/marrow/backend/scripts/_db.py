"""Sync SQLAlchemy engine for use in standalone scripts.

Scripts run outside the FastAPI event loop and need a synchronous engine.
For Postgres, we derive a sync URL by replacing '+asyncpg' with '+psycopg2'
— the same pattern Alembic's migrations/env.py uses.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _sync_url() -> str:
    """Return a sync-compatible database URL from settings."""
    url = settings.database_url
    # asyncpg is async-only; psycopg2 is the sync equivalent for Postgres.
    return url.replace("+asyncpg", "+psycopg2")


def get_sync_engine():  # type: ignore[no-untyped-def]
    """Create a sync SQLAlchemy engine from settings."""
    return create_engine(_sync_url())


def get_sync_session() -> Session:
    """Return an open (not context-managed) sync Session.

    Callers are responsible for committing and closing.
    Prefer using SyncSession() as a context manager where possible.
    """
    engine = get_sync_engine()
    factory = sessionmaker(bind=engine)
    return factory()


class SyncSession:
    """Context manager wrapping a sync SQLAlchemy Session."""

    def __init__(self) -> None:
        self._engine = get_sync_engine()
        self._factory = sessionmaker(bind=self._engine)

    def __enter__(self) -> Session:
        self._session: Session = self._factory()
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        if exc_type:
            self._session.rollback()
        else:
            self._session.commit()
        self._session.close()
        self._engine.dispose()
