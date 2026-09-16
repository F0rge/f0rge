from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

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
from cryptography.fernet import Fernet  # noqa: E402
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
from app.services.role_user_seed import RoleUserSeedService  # noqa: E402
from app.services.roles import RoleSeedService  # noqa: E402
from app.services.till_seed import TillSeedService  # noqa: E402
from app.services.users import BootstrapService  # noqa: E402

OWNER_EMAIL = settings.seed_owner_email
OWNER_PASSWORD = settings.seed_owner_password
TEST_TENANT_HOST = "testserver"
TENANT_HOST_HEADER = {"X-Tenant-Host": TEST_TENANT_HOST}
BACKEND_ROOT = Path(__file__).resolve().parent.parent

postgres_container = postgres_container_fixture("postgres:16")


@pytest.fixture(autouse=True)
def disable_nia_schedule_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "nia_schedule_ticker", False)


@pytest.fixture(autouse=True)
def patch_storage_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    monkeypatch.setattr(settings, "storage_dir", str(storage_path))


@pytest.fixture(autouse=True)
def patch_async_session_maker(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if request.node.get_closest_marker("no_db"):
        return
    async_engine = request.getfixturevalue("async_engine")
    maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.database.async_session_maker", maker)


@pytest_asyncio.fixture(scope="session")
async def async_engine(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(async_url(postgres_container), echo=False)
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)

    def _stamp_tenant_head() -> None:
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", async_url(postgres_container))
        command.stamp(cfg, "head")

    await asyncio.to_thread(_stamp_tenant_head)
    async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as session:
        await RoleSeedService(session).seed()
        await BootstrapService(session).seed_if_empty()
        await LocationSeedService(session).seed_if_empty()
        await RoleUserSeedService(session).seed()
        coa = ChartOfAccountsSeedService(session)
        await coa.seed_if_empty()
        await coa.ensure_opening_equity()
        await coa.ensure_category_chart()
        await coa.ensure_bank_accounts()
        await TillSeedService(session).seed_if_empty()
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def platform_registry(
    postgres_container: PostgresContainer,
    async_engine: AsyncEngine,
) -> AsyncIterator[str]:
    from app.platform.bootstrap_default_tenant import bootstrap_default_tenant
    from app.platform.database import dispose_platform_engines
    from app.tenancy.resolver import invalidate_hostname_cache

    if not settings.settings_encryption_key:
        settings.settings_encryption_key = Fernet.generate_key().decode()
    base_url = async_url(postgres_container)
    admin_url = f"{base_url.rsplit('/', 1)[0]}/postgres"
    db_name = "vellano_platform_suite"
    admin_engine = create_async_engine(admin_url, echo=False, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        await conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    await admin_engine.dispose()
    platform_url = f"{base_url.rsplit('/', 1)[0]}/{db_name}"
    subprocess.run(
        ["uv", "run", "alembic", "-c", "alembic_platform.ini", "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        env={**os.environ, "PLATFORM_DATABASE_URL": platform_url},
        check=True,
    )
    settings.platform_database_url = platform_url
    settings.platform_admin_database_url = admin_url
    settings.default_tenant_hostnames = [TEST_TENANT_HOST, "localhost"]
    settings.tenant_base_domain = "localhost"
    settings.database_url = async_url(postgres_container)
    await bootstrap_default_tenant()
    invalidate_hostname_cache()
    try:
        yield platform_url
    finally:
        await dispose_platform_engines()


@pytest.fixture(autouse=True)
def _require_platform_registry(
    request: pytest.FixtureRequest,
) -> None:
    if request.node.get_closest_marker("no_db"):
        return
    request.getfixturevalue("platform_registry")


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
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers=TENANT_HOST_HEADER,
    ) as client:
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
