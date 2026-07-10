from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import Base so metadata is populated.
from app.database import Base  # noqa: F401
from app.config import settings
from app.db_url import resolve_database_url

# Explicitly import every model so their tables appear in Base.metadata
# when autogenerate runs — even if nothing else imported them yet.
import app.models.dietary_ingredient  # noqa: F401
import app.models.entry  # noqa: F401
import app.models.health_metrics  # noqa: F401
import app.models.ingredient_alias  # noqa: F401
import app.models.lab  # noqa: F401
import app.models.lab_marker  # noqa: F401
import app.models.lab_marker_alias  # noqa: F401
import app.models.lab_marker_catalog  # noqa: F401
import app.models.photo  # noqa: F401
import app.models.photo_analysis  # noqa: F401
import app.models.photo_ingredient  # noqa: F401
import app.models.session  # noqa: F401
import app.models.supplement_catalog  # noqa: F401
import app.models.symptom_catalog  # noqa: F401
import app.models.treatment  # noqa: F401
import app.models.weather  # noqa: F401
import app.models.user_settings  # noqa: F401
import app.models.embedding  # noqa: F401
import app.models.user  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL to stdout, no live DB."""
    context.configure(
        url=resolve_database_url(
            settings.database_url,
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
    """Run migrations in 'online' mode using the async engine from settings."""
    engine = create_async_engine(
        resolve_database_url(
            settings.database_url,
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
    asyncio.run(run_migrations_online())
