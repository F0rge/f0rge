from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from f0rge_db.db_url import resolve_database_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.database import Base  # noqa: F401

import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    # The release runner embeds Alembic in-process. Preserve application
    # loggers, including request diagnostics, across that configuration step.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode — emits SQL to stdout, no live DB."""
    context.configure(
        url=resolve_database_url(
            os.environ.get("MIGRATION_DATABASE_URL") or settings.database_url,
            direct_url=settings.direct_database_url,
        ),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in online mode using the async engine from settings."""
    engine = create_async_engine(
        resolve_database_url(
            os.environ.get("MIGRATION_DATABASE_URL") or settings.database_url,
            direct_url=settings.direct_database_url,
        ),
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    connection = config.attributes.get("connection")
    if connection is not None:
        # The release runner supplies one locked transaction for migrations
        # and their durable acknowledgement. Ordinary Alembic CLI is unchanged.
        do_run_migrations(connection)
    else:
        asyncio.run(run_migrations_online())
