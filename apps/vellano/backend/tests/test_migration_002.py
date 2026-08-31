"""Regression: migration 002 CHECK expects lowercase role values in DB."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import AsyncIterator

import pytest
import sqlalchemy as sa
from f0rge_testing import async_url
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.config import settings
from app.database import get_db
from app.main import app
from app.services.users import BootstrapService
from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.asyncio
async def test_migration_002_seed_stores_lowercase_role(
    postgres_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = async_url(postgres_container)
    admin_url = f"{base_url.rsplit('/', 1)[0]}/postgres"
    db_name = "vellano_mig002"

    admin_engine = create_async_engine(admin_url, echo=False, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        await conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    await admin_engine.dispose()

    mig_url = f"{base_url.rsplit('/', 1)[0]}/{db_name}"
    monkeypatch.setenv("DATABASE_URL", mig_url)
    monkeypatch.setattr(settings, "database_url", mig_url)

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": mig_url},
        check=True,
    )

    engine = create_async_engine(mig_url, echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.database.async_session_maker", maker)
    monkeypatch.setattr("app.main.async_session_maker", maker)

    async with maker() as session:
        await BootstrapService(session).seed_if_empty()

    async with engine.connect() as conn:
        role = (await conn.execute(sa.text("SELECT role FROM users LIMIT 1"))).scalar_one()
    assert role == "owner"
    await engine.dispose()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
        )
        assert login.status_code == 200
        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["role"] == "owner"
    app.dependency_overrides.clear()
