from __future__ import annotations

import uuid

import jwt
import pytest
import sqlalchemy as sa
from f0rge_testing import async_url
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.database import Base, get_db
from app.main import app
from app.platform.database import platform_sessionmaker
from app.platform.models import TENANT_STATUS_READY, Tenant, TenantHostname
from app.platform.service import encrypt_database_url
from app.services.auth import JWT_ALGORITHM, JWT_COOKIE_NAME, _require_jwt_secret
from app.services.roles import RoleSeedService
from app.services.users import BootstrapService
from app.tenancy.engines import engine_cache
from app.tenancy.resolver import invalidate_hostname_cache
from f0rge_db.crud import unit_of_work
from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD, TEST_TENANT_HOST


async def _create_db(postgres_container: PostgresContainer, name: str) -> str:
    base_url = async_url(postgres_container)
    admin_url = f"{base_url.rsplit('/', 1)[0]}/postgres"
    engine = create_async_engine(admin_url, echo=False, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
        await conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()
    return f"{base_url.rsplit('/', 1)[0]}/{name}"


async def _seed_owner_db(url: str) -> None:
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await RoleSeedService(session).seed()
        await BootstrapService(session).seed_if_empty()
    await engine.dispose()


async def _register_tenant(
    *, slug: str, hostname: str, database_url: str, prefix: str
) -> uuid.UUID:
    maker = platform_sessionmaker()
    async with maker() as db:
        async with unit_of_work(db):
            tenant = Tenant(
                slug=slug,
                display_name=slug,
                status=TENANT_STATUS_READY,
                database_url_encrypted=encrypt_database_url(database_url),
                storage_prefix=prefix,
            )
            db.add(tenant)
            await db.flush()
            db.add(
                TenantHostname(hostname=hostname, tenant_id=tenant.id, is_primary=True),
            )
            tenant_id = tenant.id
    invalidate_hostname_cache()
    return tenant_id


def _raw_client(**headers: str) -> AsyncClient:
    app.dependency_overrides.pop(get_db, None)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers=headers,
    )


@pytest.mark.asyncio
async def test_skus_without_tenant_header_are_404(platform_registry: str) -> None:
    async with _raw_client() as client:
        resp = await client.get("/api/v1/skus")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "tenant_not_found"


@pytest.mark.asyncio
async def test_unknown_tenant_host_is_404(platform_registry: str) -> None:
    async with _raw_client(**{"X-Tenant-Host": "nope.localhost"}) as client:
        resp = await client.get("/api/v1/skus")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "tenant_not_found"


@pytest.mark.asyncio
async def test_skus_with_header_and_no_cookie_are_401(platform_registry: str) -> None:
    async with _raw_client(**{"X-Tenant-Host": "localhost"}) as client:
        resp = await client.get("/api/v1/skus")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_jwt_includes_tid_and_me_works(
    owner_client: AsyncClient,
    platform_registry: str,
) -> None:
    login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert login.status_code == 200
    token = login.cookies.get(JWT_COOKIE_NAME)
    assert token
    payload = jwt.decode(token, _require_jwt_secret(), algorithms=[JWT_ALGORITHM])
    assert payload.get("tid")
    uuid.UUID(str(payload["tid"]))
    me = await owner_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    branding = await owner_client.get("/api/v1/branding")
    assert branding.status_code == 200
    assert branding.json()["slug"] == "vellano"


@pytest.mark.asyncio
async def test_token_without_tid_is_401(
    async_client: AsyncClient,
    platform_registry: str,
) -> None:
    token = jwt.encode(
        {"sub": str(uuid.uuid4())},
        _require_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
    async_client.cookies.set(JWT_COOKIE_NAME, token)
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cookie_replay_across_tenants_is_401(
    postgres_container: PostgresContainer,
    platform_registry: str,
) -> None:
    url_b = await _create_db(postgres_container, "vellano_tenancy_b")
    await _seed_owner_db(url_b)
    await _register_tenant(
        slug="tenb",
        hostname="b.testserver",
        database_url=url_b,
        prefix=f"tenants/{uuid.uuid4()}",
    )
    try:
        async with _raw_client(**{"X-Tenant-Host": TEST_TENANT_HOST}) as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
            )
            assert login.status_code == 200
            replay = await client.get(
                "/api/v1/skus",
                headers={"X-Tenant-Host": "b.testserver"},
            )
            assert replay.status_code == 401
    finally:
        await engine_cache.dispose_all()


@pytest.mark.asyncio
async def test_sku_on_tenant_a_is_absent_from_b(
    postgres_container: PostgresContainer,
    platform_registry: str,
) -> None:
    url_a = await _create_db(postgres_container, "vellano_tenancy_iso_a")
    url_b = await _create_db(postgres_container, "vellano_tenancy_iso_b")
    await _seed_owner_db(url_a)
    await _seed_owner_db(url_b)
    await _register_tenant(
        slug="iso-a",
        hostname="a.testserver",
        database_url=url_a,
        prefix=f"tenants/{uuid.uuid4()}",
    )
    await _register_tenant(
        slug="iso-b",
        hostname="c.testserver",
        database_url=url_b,
        prefix=f"tenants/{uuid.uuid4()}",
    )
    payload = {
        "our_ref": "ISO-A-1",
        "our_barcode": "ISO-BAR-A",
        "name": "Tenant A sofa",
        "design": "Iso",
        "fabric": "Linen",
    }
    try:
        async with _raw_client(**{"X-Tenant-Host": "a.testserver"}) as client_a:
            login = await client_a.post(
                "/api/v1/auth/login",
                json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
            )
            assert login.status_code == 200
            created = await client_a.post("/api/v1/skus", json=payload)
            assert created.status_code == 201
            listed_a = await client_a.get("/api/v1/skus")
            assert listed_a.status_code == 200
            assert any(row["our_ref"] == "ISO-A-1" for row in listed_a.json())

        async with _raw_client(**{"X-Tenant-Host": "c.testserver"}) as client_b:
            login_b = await client_b.post(
                "/api/v1/auth/login",
                json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
            )
            assert login_b.status_code == 200
            listed_b = await client_b.get("/api/v1/skus")
            assert listed_b.status_code == 200
            assert listed_b.json() == []
    finally:
        await engine_cache.dispose_all()
