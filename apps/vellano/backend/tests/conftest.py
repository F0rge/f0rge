from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-pytest-only-32b")

from typing import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from f0rge_testing import async_url, postgres_container_fixture, savepoint_session  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

import app.models  # noqa: F401, E402

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth import JWT_COOKIE_NAME  # noqa: E402
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService  # noqa: E402
from app.services.till_seed import TillSeedService  # noqa: E402
from app.services.users import BootstrapService  # noqa: E402

OWNER_EMAIL = settings.seed_owner_email
OWNER_PASSWORD = settings.seed_owner_password

postgres_container = postgres_container_fixture("postgres:16")


@pytest.fixture(autouse=True)
def patch_storage_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    monkeypatch.setattr(settings, "storage_dir", str(storage_path))


@pytest.fixture(autouse=True)
def patch_async_session_maker(
    async_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.database.async_session_maker", maker)
    monkeypatch.setattr("app.main.async_session_maker", maker)


@pytest_asyncio.fixture(scope="session")
async def async_engine(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(async_url(postgres_container), echo=False)
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as session:
        await BootstrapService(session).seed_if_empty()
        await LocationSeedService(session).seed_if_empty()
        await ChartOfAccountsSeedService(session).seed_if_empty()
        await TillSeedService(session).seed_if_empty()
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def async_db(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with savepoint_session(async_engine) as session:
        yield session


@pytest_asyncio.fixture
async def async_client(async_db: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield async_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def owner_client(async_client: AsyncClient) -> AsyncClient:
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert resp.status_code == 200
    return async_client


def assert_vellano_session_cookie(resp: httpx.Response) -> None:
    set_cookie = resp.headers.get("set-cookie", "")
    assert JWT_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie or "SameSite=Lax" in set_cookie
