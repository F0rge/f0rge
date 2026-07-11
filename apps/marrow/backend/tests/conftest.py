"""Shared pytest fixtures for the backend test suite.

Container + savepoint machinery comes from ``f0rge_testing``; everything
app-specific (extensions, schema, RLS enablement, catalog seeding, default
user, ASGI clients, jwt patch) stays here.

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

import os

# Pin a Postgres-flavoured placeholder DATABASE_URL before any app import.
# ``app/database.py`` constructs an ``AsyncEngine`` at module-load time using
# ``settings.database_url``; we don't want that to inadvertently pick up a
# ``sqlite+aiosqlite://`` value from the developer's local ``.env``. The real
# engine the tests use is built below against a freshly spawned testcontainer.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
)

import uuid
from typing import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from f0rge_db.auth_context import user_id_ctx  # noqa: E402
from f0rge_db.tenant import apply_session_user_id  # noqa: E402
from f0rge_testing import async_url, postgres_container_fixture, savepoint_session  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # noqa: E402

# Import models so Base.metadata knows every table before create_all runs.
import app.models  # noqa: F401, E402

from app.config import settings
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH  # noqa: E402
from app.rls import enable_row_level_security
from app.sql.copy_reference_catalogs import COPY_USER_CATALOG_FROM_REFERENCE_SQL

TEST_JWT_SECRET = "test-jwt-secret-for-pytest-only-32b"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test-password-12"


# ---------------------------------------------------------------------------
# Session-scoped containers + engine
# ---------------------------------------------------------------------------

postgres_container = postgres_container_fixture("pgvector/pgvector:pg16")


@pytest_asyncio.fixture(scope="session")
async def async_engine(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    """One AsyncEngine for the whole session, with the schema created."""
    engine = create_async_engine(async_url(postgres_container), echo=False)
    async with engine.begin() as conn:
        # pgvector extension must be installed before any VECTOR column can be created.
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)
        await enable_row_level_security(conn)
        await conn.execute(sa.text(COPY_USER_CATALOG_FROM_REFERENCE_SQL))
        await conn.execute(
            sa.text(
                """
                INSERT INTO users (id, email, password_hash, avatar_default_index, created_at)
                VALUES (:id, :email, :password_hash, :avatar_default_index, now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": settings.default_storage_user_id,
                "email": "leo@health-tracker.local",
                "password_hash": LEO_PLACEHOLDER_PASSWORD_HASH,
                "avatar_default_index": 0,
            },
        )
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

    Savepoint machinery lives in ``f0rge_testing.savepoint_session``; here we
    only layer marrow's tenant context (ContextVar + ``app.user_id`` GUC) on top.
    """
    async with savepoint_session(async_engine) as session:
        user_token = user_id_ctx.set(uuid.UUID(settings.default_storage_user_id))
        try:
            await apply_session_user_id(session, uuid.UUID(settings.default_storage_user_id))
            yield session
        finally:
            user_id_ctx.reset(user_token)


# ---------------------------------------------------------------------------
# Function-scoped HTTP client (kept for future tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(async_db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """An ``httpx.AsyncClient`` wired to the FastAPI app with ``get_db`` overridden."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        user_id = user_id_ctx.get()
        if user_id is not None:
            await apply_session_user_id(async_db, user_id)
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", TEST_JWT_SECRET)


@pytest.fixture
async def authed_client(async_client: AsyncClient) -> AsyncClient:
    """Log in via a real signup round-trip (rolled back with the test savepoint)."""
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    return async_client


async def authed_user_id(client: httpx.AsyncClient) -> uuid.UUID:
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    return uuid.UUID(me.json()["user_id"])
