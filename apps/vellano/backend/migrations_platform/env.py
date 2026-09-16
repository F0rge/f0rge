from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from f0rge_db.db_url import resolve_database_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.platform.models import PlatformBase

import app.platform.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = PlatformBase.metadata
VERSION_TABLE = "alembic_version_platform"


def _platform_url() -> str:
    override = config.get_main_option("sqlalchemy.url")
    if override and not override.startswith("driver://"):
        return resolve_database_url(override, direct_url="")
    return resolve_database_url(
        settings.platform_database_url,
        direct_url=settings.platform_direct_database_url,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_platform_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_platform_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
