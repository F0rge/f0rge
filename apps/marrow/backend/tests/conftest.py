"""Shared pytest fixtures for the backend test suite.

Container + savepoint machinery comes from ``f0rge_testing``; everything
app-specific (extensions, schema, RLS enablement, catalog seeding, default
user, ASGI clients, jwt patch) stays here.

Provides:
- ``postgres_container`` — session-scoped real Postgres (testcontainers, pgvector/pg16 image)
- ``superuser_engine``   — session-scoped AsyncEngine (container superuser) for schema
                           bootstrap and tests that must seed cross-tenant rows
- ``async_engine``       — session-scoped AsyncEngine for the ``test_app`` NOSUPERUSER role;
                           app-facing sessions use this so RLS is actually enforced
- ``async_db``            — function-scoped ``AsyncSession`` running inside a SAVEPOINT
                           that is rolled back after the test, giving per-test isolation
                           without truncating tables
- ``async_client``        — function-scoped ``httpx.AsyncClient`` against the FastAPI app
                           with ``get_db`` overridden to yield ``async_db``

Tests in this repo call services directly (no TestClient). The ``async_client``
fixture is provided for future HTTP-level tests but isn't required by the current
suite.

Cross-user assertions on a shared ``async_db`` session must set the GUC via
``apply_session_user_id`` (or go through HTTP clients). The session GUC follows
the last ``apply_session_user_id`` call — see issue #308.
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

import contextlib
import uuid
from typing import AsyncIterator  # noqa: E402

pytest_plugins = ["tests.cache_helpers"]

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from f0rge_db.auth_context import user_id_ctx  # noqa: E402
from f0rge_db.tenant import apply_session_user_id  # noqa: E402
from f0rge_testing import async_url, postgres_container_fixture, savepoint_session  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # noqa: E402

# Import models so Base.metadata knows every table before create_all runs.
import app.models  # noqa: F401, E402

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH  # noqa: E402
from app.rls import enable_row_level_security, enable_social_security  # noqa: E402
from app.sql.copy_reference_catalogs import COPY_USER_CATALOG_FROM_REFERENCE_SQL  # noqa: E402
from tests.helpers import signup_payload  # noqa: E402

TEST_JWT_SECRET = "test-jwt-secret-for-pytest-only-32b"

TEST_APP_ROLE = "test_app"
TEST_APP_PASSWORD = "test"

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test-password-12"
TEST_HANDLE = "test_user"


# ---------------------------------------------------------------------------
# Session-scoped containers + engine
# ---------------------------------------------------------------------------

postgres_container = postgres_container_fixture("pgvector/pgvector:pg16")


def test_app_async_url(container: PostgresContainer) -> str:
    """Connection URL for the NOSUPERUSER role used by app-facing test sessions."""
    url = async_url(container)
    return url.replace("://postgres:postgres@", f"://{TEST_APP_ROLE}:{TEST_APP_PASSWORD}@")


async def _provision_test_app_role(conn: AsyncConnection) -> None:
    """Create ``test_app`` with the same table/sequence/function grants as migration 019."""
    await conn.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{TEST_APP_ROLE}') THEN
                    CREATE ROLE {TEST_APP_ROLE}
                        WITH LOGIN PASSWORD '{TEST_APP_PASSWORD}'
                        NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
                END IF;
            END
            $$;
            """
        )
    )
    await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {TEST_APP_ROLE}"))
    await conn.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            f"TO {TEST_APP_ROLE}"
        )
    )
    await conn.execute(
        sa.text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {TEST_APP_ROLE}")
    )
    await conn.execute(
        sa.text(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {TEST_APP_ROLE}")
    )


@pytest_asyncio.fixture(scope="session")
async def superuser_engine(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    """Superuser engine — schema bootstrap and cross-tenant seeding only."""
    engine = create_async_engine(async_url(postgres_container), echo=False)
    async with engine.begin() as conn:
        # pgvector extension must be installed before any VECTOR column can be created.
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)
        await enable_row_level_security(conn)
        await enable_social_security(conn)
        await _provision_test_app_role(conn)
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


@pytest_asyncio.fixture(scope="session")
async def async_engine(
    superuser_engine: AsyncEngine,
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    """App-facing engine — ``test_app`` NOSUPERUSER so RLS policies apply."""
    _ = superuser_engine  # ensure bootstrap finished before connecting as test_app
    engine = create_async_engine(test_app_async_url(postgres_container), echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()


# Modules that bind ``async_session_maker`` at import time — patch per test so
# background tasks use the testcontainer ``test_app`` engine, not ``.env`` URL.
_BACKGROUND_SESSION_MODULES = (
    "app.services.tag_delivery",
    "app.services.food_analysis_orchestrator",
    "app.embedding_pipeline.worker",
    "app.embedding_pipeline.backfill",
)


@pytest.fixture(autouse=True)
def patch_background_session_maker(
    async_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    for module in _BACKGROUND_SESSION_MODULES:
        monkeypatch.setattr(f"{module}.async_session_maker", real_maker)


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


@pytest.fixture
def patch_reminder_session_maker(async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Route the reminder tick's own session onto the test savepoint session.

    ``nullcontext`` is an async context manager since 3.10, so it stands in for
    ``async_session_maker()`` without closing ``async_db`` on exit.
    """
    monkeypatch.setattr(
        "app.services.reminders.async_session_maker",
        lambda: contextlib.nullcontext(async_db),
    )


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


@pytest.fixture(autouse=True)
def stub_open_meteo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep suite HTTP-free: entry creates must not call Open-Meteo.

    Weather-specific tests remonkeypatch ``app.services.weather.fetch_open_meteo_day``.
    """

    async def _no_weather(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.services.weather.fetch_open_meteo_day", _no_weather)


@pytest.fixture
async def authed_client(async_client: AsyncClient) -> AsyncClient:
    """Log in via a real signup round-trip (rolled back with the test savepoint)."""
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD, TEST_HANDLE),
    )
    assert resp.status_code == 200
    return async_client


async def authed_user_id(client: httpx.AsyncClient) -> uuid.UUID:
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    return uuid.UUID(me.json()["user_id"])
