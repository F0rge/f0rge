"""Alembic upgrade-head harness.

Uses an isolated module-scoped Postgres container (same pattern as
test_migration_006) and runs the full migration chain via Alembic's
command API — the same path Fly release_command uses in production.
"""

from __future__ import annotations

from typing import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer


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
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def test_alembic_upgrade_head(migration_postgres_container: PostgresContainer) -> None:
    sync_url = _sync_url(migration_postgres_container)
    engine = create_engine(sync_url)

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", _async_url(migration_postgres_container))

    command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version, "alembic_version should be set after upgrade head"

        # Spot-check a late migration table exists.
        has_users = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='users'"
            )
        ).fetchone()
        assert has_users, "users table missing after upgrade head"

    engine.dispose()
