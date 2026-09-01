"""Regression: migration 004 creates catalogue tables."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa
from f0rge_testing import async_url
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer

from app.config import settings

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.asyncio
async def test_migration_004_creates_catalogue_tables(
    postgres_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = async_url(postgres_container)
    admin_url = f"{base_url.rsplit('/', 1)[0]}/postgres"
    db_name = "vellano_mig004"

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
    async with engine.connect() as conn:
        tables = (
            await conn.execute(
                sa.text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name IN "
                    "('suppliers', 'proformas', 'skus') ORDER BY table_name"
                )
            )
        ).fetchall()
    await engine.dispose()

    assert [row[0] for row in tables] == ["proformas", "skus", "suppliers"]
