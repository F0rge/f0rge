"""Alembic upgrade-head harness.

Uses an isolated module-scoped Postgres container (same pattern as
test_migration_006) and runs the full migration chain via Alembic CLI —
the same path Fly release_command uses in production.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def migration_postgres_container() -> Iterator[PostgresContainer]:
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        yield container
    finally:
        container.stop()


def _sync_url(container: PostgresContainer) -> str:
    url = container.get_connection_url()
    if "+psycopg2" not in url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _async_url(container: PostgresContainer) -> str:
    url = container.get_connection_url()
    if "+asyncpg" in url:
        return url
    if "+psycopg2" in url:
        return url.replace("+psycopg2", "+asyncpg", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def test_alembic_upgrade_head(migration_postgres_container: PostgresContainer) -> None:
    sync_url = _sync_url(migration_postgres_container)
    async_url = _async_url(migration_postgres_container)
    engine = create_engine(sync_url)

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    env = os.environ.copy()
    env["DATABASE_URL"] = async_url
    env.setdefault("JWT_SECRET", "migration-test-jwt-secret-32-chars")
    env.setdefault("HEALTHTRACKER_RO_PASSWORD", "test-ro")
    env.setdefault("HEALTHTRACKER_APP_PASSWORD", "test-app")

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_BACKEND_ROOT,
        env=env,
        check=True,
    )

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version, "alembic_version should be set after upgrade head"

        has_users = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='users'"
            )
        ).fetchone()
        assert has_users, "users table missing after upgrade head"

        for table in ("hypotheses", "n_of_1_slots"):
            present = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=:table"
                ),
                {"table": table},
            ).fetchone()
            assert present, f"{table} missing after upgrade head"

    engine.dispose()
