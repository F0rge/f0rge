from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet
from f0rge_core.exceptions import ValidationError
from f0rge_testing import async_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.config import settings
from app.platform.crud import TenantCRUD
from app.platform.models import TENANT_STATUS_PROVISIONING, Tenant, TenantHostname
from app.platform.service import (
    decrypt_database_url,
    encrypt_database_url,
    normalise_hostname,
    resolve_tenant_by_hostname,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme.Example.COM", "acme.example.com"),
        ("acme.example.com:443", "acme.example.com"),
        ("localhost:3003", "localhost"),
        ("vellano.localhost.", "vellano.localhost"),
    ],
)
def test_normalise_hostname(raw: str, expected: str) -> None:
    assert normalise_hostname(raw) == expected


@pytest.mark.no_db
@pytest.mark.parametrize("raw", ["", "*", "   ", "http://evil"])
def test_normalise_hostname_rejects_junk(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalise_hostname(raw)


@pytest.mark.no_db
def test_encrypt_database_url_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "settings_encryption_key", key)
    url = "postgresql+asyncpg://tenant_acme:secret@localhost:5433/tenant_acme"
    token = encrypt_database_url(url)
    assert "secret" not in token
    assert decrypt_database_url(token) == url


async def _create_db(admin_url: str, name: str) -> str:
    engine = create_async_engine(admin_url, echo=False, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
        await conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()
    return f"{admin_url.rsplit('/', 1)[0]}/{name}"


def _upgrade_platform(url: str) -> None:
    subprocess.run(
        ["uv", "run", "alembic", "-c", "alembic_platform.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env={**os.environ, "PLATFORM_DATABASE_URL": url},
        check=True,
    )


@pytest.mark.asyncio
async def test_platform_alembic_creates_registry_tables(
    postgres_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = async_url(postgres_container)
    admin_url = f"{base_url.rsplit('/', 1)[0]}/postgres"
    url = await _create_db(admin_url, "vellano_platform_alembic")
    monkeypatch.setattr(settings, "platform_database_url", url)
    _upgrade_platform(url)
    _upgrade_platform(url)
    engine = create_async_engine(url, echo=False)
    async with engine.connect() as conn:
        tables = set(
            (
                await conn.execute(
                    sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
            ).scalars()
        )
    await engine.dispose()
    assert "tenants" in tables
    assert "tenant_hostnames" in tables
    assert "signups" in tables
    assert "alembic_version_platform" in tables


@pytest.mark.asyncio
async def test_resolve_provisioning_tenant_is_hidden(
    postgres_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "settings_encryption_key", key)
    base_url = async_url(postgres_container)
    admin_url = f"{base_url.rsplit('/', 1)[0]}/postgres"
    url = await _create_db(admin_url, "vellano_platform_resolve")
    monkeypatch.setattr(settings, "platform_database_url", url)
    _upgrade_platform(url)
    engine = create_async_engine(url, echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        tenant = Tenant(
            slug="acme",
            display_name="Acme",
            status=TENANT_STATUS_PROVISIONING,
            database_url_encrypted=encrypt_database_url(settings.database_url),
            storage_prefix="tenants/acme",
        )
        db.add(tenant)
        await db.flush()
        db.add(TenantHostname(hostname="acme.testserver", tenant_id=tenant.id, is_primary=True))
        await db.commit()
        found = await resolve_tenant_by_hostname(db, "ACME.testserver:443")
        assert found is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_default_tenant_is_idempotent(
    postgres_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.platform.bootstrap_default_tenant import bootstrap_default_tenant
    from app.platform.database import dispose_platform_engines

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "settings_encryption_key", key)
    base_url = async_url(postgres_container)
    admin_url = f"{base_url.rsplit('/', 1)[0]}/postgres"
    platform_url = await _create_db(admin_url, "vellano_platform_boot")
    tenant_url = await _create_db(admin_url, "vellano_tenant_boot")
    monkeypatch.setattr(settings, "platform_database_url", platform_url)
    monkeypatch.setattr(settings, "database_url", tenant_url)
    monkeypatch.setattr(settings, "tenant_base_domain", "localhost")
    monkeypatch.setattr(settings, "default_tenant_slug", "vellano")
    monkeypatch.setattr(settings, "default_tenant_hostnames", ["localhost"])
    monkeypatch.setattr(settings, "default_storage_user_id", "vellano")
    _upgrade_platform(platform_url)
    first = await bootstrap_default_tenant()
    second = await bootstrap_default_tenant()
    assert first.id == second.id
    engine = create_async_engine(platform_url, echo=False)
    async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as db:
        tenants = await TenantCRUD(db).list_ready()
        assert len(tenants) == 1
        hosts = {h.hostname for h in tenants[0].hostnames}
        assert hosts == {"localhost", "vellano.localhost"}
        assert tenants[0].status == "ready"
    await engine.dispose()
    await dispose_platform_engines()


@pytest.mark.asyncio
async def test_bootstrap_refuses_platform_url_equal_to_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.platform.bootstrap_default_tenant import BootstrapError, bootstrap_default_tenant

    url = "postgresql+asyncpg://vellano:vellano@localhost:5433/vellano"
    monkeypatch.setattr(settings, "platform_database_url", url)
    monkeypatch.setattr(settings, "database_url", url)
    with pytest.raises(BootstrapError):
        await bootstrap_default_tenant()


@pytest.mark.no_db
def test_tenant_alembic_head_unchanged() -> None:
    result = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "052_lookbook_events" in result.stdout
    assert "p001_platform_registry" not in result.stdout
