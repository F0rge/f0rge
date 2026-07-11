from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer


def postgres_container_fixture(image: str) -> Callable[[], Iterator[PostgresContainer]]:
    """Return a session-scoped pytest fixture spawning a real Postgres container.

    Assign the result at module level in a conftest to register it::

        postgres_container = postgres_container_fixture("pgvector/pgvector:pg16")
    """

    @pytest.fixture(scope="session")
    def postgres_container() -> Iterator[PostgresContainer]:
        container = PostgresContainer(image)
        container.start()
        try:
            yield container
        finally:
            container.stop()

    return postgres_container


def async_url(container: PostgresContainer) -> str:
    """Convert the container's sync psycopg2 URL into an asyncpg URL."""
    url = container.get_connection_url()
    # testcontainers gives us postgresql+psycopg2://; swap to asyncpg.
    if "+psycopg2" in url:
        url = url.replace("+psycopg2", "+asyncpg")
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@asynccontextmanager
async def savepoint_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """An ``AsyncSession`` whose writes are rolled back on exit — per-test isolation.

    Pattern: open a connection, begin an outer transaction, bind a session to
    that connection with ``join_transaction_mode="create_savepoint"`` so every
    session-level ``commit()`` only releases a SAVEPOINT, then on exit roll
    back the outer transaction so nothing persists across tests.
    """
    async with engine.connect() as conn:
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
