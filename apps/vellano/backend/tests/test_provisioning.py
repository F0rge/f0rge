from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app.platform.database import platform_sessionmaker
from app.platform.models import SIGNUP_STATUS_VERIFIED, Signup
from app.platform.provisioning import ProvisioningService
from app.platform.migrate_all import migrate_all
from app.services.auth import hash_password
from f0rge_db.crud import unit_of_work
from tests.test_tenancy_routing import _raw_client


async def _verified_signup(slug: str, email: str, password: str, legal_name: str) -> uuid.UUID:
    maker = platform_sessionmaker()
    async with maker() as db:
        signup = Signup(
            email=email,
            legal_name=legal_name,
            trading_name=legal_name,
            slug=slug,
            owner_name="Owner",
            password_hash=hash_password(password),
            status=SIGNUP_STATUS_VERIFIED,
            privacy_version="2026-09-draft",
            authorised_confirmed_at=datetime.datetime.utcnow(),
            verified_at=datetime.datetime.utcnow(),
        )
        async with unit_of_work(db):
            db.add(signup)
            await db.flush()
        return signup.id


@pytest.mark.asyncio
async def test_provision_is_idempotent_and_home_is_empty(
    postgres_container,
    platform_registry: str,
) -> None:
    slug = "provacme"
    email = "owner@provacme.example"
    password = "correct horse battery staple"
    signup_id = await _verified_signup(slug, email, password, "Prov Acme (Pty) Ltd")
    service = ProvisioningService()
    first = await service.provision(signup_id)
    second = await service.provision(signup_id)
    assert first.id == second.id
    assert first.status == "ready"
    assert second.status == "ready"

    from app.platform.service import decrypt_database_url

    url = decrypt_database_url(first.database_url_encrypted or "")
    engine = create_async_engine(url, echo=False)
    async with engine.connect() as conn:
        users = (await conn.execute(sa.text("SELECT count(*) FROM users"))).scalar_one()
        locations = (await conn.execute(sa.text("SELECT count(*) FROM locations"))).scalar_one()
        team_name = (await conn.execute(sa.text("SELECT name FROM teams LIMIT 1"))).scalar_one()
        emails = list((await conn.execute(sa.text("SELECT email FROM users"))).scalars())
    await engine.dispose()
    assert int(users) == 1
    assert int(locations) == 0
    assert team_name == "Prov Acme (Pty) Ltd"
    assert emails == [email]
    assert not any(str(row).endswith("@example.com") for row in emails)

    async with _raw_client(**{"X-Tenant-Host": f"{slug}.localhost"}) as client:
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        skus = await client.get("/api/v1/skus")
        assert skus.status_code == 200
        assert skus.json() == []

    assert await migrate_all(only=slug) == 0


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_migrate_all_without_platform_url_uses_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings
    from app.platform import migrate_all as mod

    seen: list[str] = []

    def fake_upgrade_tenant(database_url: str) -> None:
        seen.append(database_url)

    monkeypatch.setattr(settings, "platform_database_url", "")
    monkeypatch.setattr(mod, "_upgrade_tenant", fake_upgrade_tenant)
    monkeypatch.setattr(mod, "_upgrade_platform", lambda: seen.append("platform"))
    assert await mod.migrate_all() == 0
    assert seen == [settings.database_url]
