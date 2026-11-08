"""Migrated lowercase roles still authorize through real signed Clerk HTTP."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from f0rge_testing import async_url
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.team import Team
from app.models.user import User
from app.services.users import BootstrapService
from tests.conftest import OWNER_EMAIL, signed_clerk_token

pytestmark = pytest.mark.no_db
BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.asyncio
async def test_migration_002_seed_stores_lowercase_role(
    postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = async_url(postgres_container)
    db_name = "firstout_mig002_" + uuid.uuid4().hex
    admin_url = make_url(base_url).set(database="postgres").render_as_string(hide_password=False)
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    mig_url = make_url(base_url).set(database=db_name).render_as_string(hide_password=False)
    monkeypatch.setattr(settings, "database_url", mig_url)
    engine = create_async_engine(mig_url)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    previous = app.dependency_overrides.get(get_db)
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env={**os.environ, "DATABASE_URL": mig_url, "MIGRATION_DATABASE_URL": mig_url},
            check=True,
        )
        monkeypatch.setattr("app.database.async_session_maker", maker)
        monkeypatch.setattr("app.main.async_session_maker", maker)
        async with maker() as session:
            await BootstrapService(session).seed_if_empty()
            user = await session.scalar(sa.select(User).where(User.email == OWNER_EMAIL))
            team = await session.get(Team, user.team_id)
            assert user.role == "owner"
            user.clerk_user_id = "user_migration002"
            team.clerk_org_id = "org_migration002"
            slug = team.slug
            await session.commit()

        async def request_db():
            async with maker() as session:
                yield session

        app.dependency_overrides[get_db] = request_db
        token = signed_clerk_token("user_migration002", org_id="org_migration002", org_slug=slug)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer " + token}
            )
            assert response.status_code == 200
            assert response.json()["role"] == "owner"
            assert response.json()["email"] == OWNER_EMAIL
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'DROP DATABASE "{db_name}" WITH (FORCE)'))
        await admin.dispose()
