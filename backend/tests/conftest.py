"""Shared pytest fixtures for the backend test suite.

Provides:
- ``postgres_container`` — session-scoped real Postgres (testcontainers, pgvector/pg16 image)
- ``async_engine``       — session-scoped AsyncEngine bound to that container with the
                           full ORM schema created via ``Base.metadata.create_all``
- ``async_db``            — function-scoped ``AsyncSession`` running inside a SAVEPOINT
                           that is rolled back after the test, giving per-test isolation
                           without truncating tables
- ``async_client``        — function-scoped ``httpx.AsyncClient`` against the FastAPI app
                           with ``get_db`` overridden to yield ``async_db``

Tests in this repo call services directly (no TestClient). The ``async_client``
fixture is provided for future HTTP-level tests but isn't required by the current
suite.
"""

from __future__ import annotations

from typing import AsyncIterator, Iterator

import httpx
import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

# Import models so Base.metadata knows every table before create_all runs.
import app.models  # noqa: F401

from app.database import Base, get_db
from app.main import app


# ---------------------------------------------------------------------------
# Session-scoped containers + engine
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Spawn a real Postgres (pgvector/pg16) for the duration of the test session."""
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        yield container
    finally:
        container.stop()


def _async_url(container: PostgresContainer) -> str:
    """Convert the container's sync psycopg2 URL into an asyncpg URL."""
    url = container.get_connection_url()
    # testcontainers gives us postgresql+psycopg2://; swap to asyncpg.
    if "+psycopg2" in url:
        url = url.replace("+psycopg2", "+asyncpg")
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest_asyncio.fixture(scope="session")
async def async_engine(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    """One AsyncEngine for the whole session, with the schema created."""
    engine = create_async_engine(_async_url(postgres_container), echo=False)
    async with engine.begin() as conn:
        # pgvector extension must be installed before any VECTOR column can be created.
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped per-test session inside a SAVEPOINT
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_db(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A function-scoped ``AsyncSession`` that rolls back at the end of the test.

    Pattern: open a connection, begin an outer transaction, bind a session to
    that connection, begin a nested transaction (SAVEPOINT) that the session
    flushes into, then on teardown roll back the outer transaction so nothing
    persists across tests.
    """
    async with async_engine.connect() as conn:
        outer = await conn.begin()
        session_maker = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint",
        )
        session = session_maker()
        try:
            yield session
        finally:
            await session.close()
            if outer.is_active:
                await outer.rollback()


# ---------------------------------------------------------------------------
# Function-scoped HTTP client (kept for future tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(async_db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """An ``httpx.AsyncClient`` wired to the FastAPI app with ``get_db`` overridden."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
