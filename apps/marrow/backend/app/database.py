from __future__ import annotations

from typing import AsyncIterator

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session

from app.auth_context import user_id_ctx
from app.config import settings
from app.db_url import asyncpg_connect_args, resolve_database_url
from app.tenant import apply_session_user_id, clear_tenant_session

_db_url = resolve_database_url(
    settings.database_url,
    direct_url=settings.direct_database_url,
)
_engine_kwargs = {"echo": False}
_connect_args = asyncpg_connect_args(settings.database_url)
if _connect_args:
    _engine_kwargs["connect_args"] = _connect_args

engine: AsyncEngine = create_async_engine(_db_url, **_engine_kwargs)

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@event.listens_for(Session, "after_begin")
def _apply_tenant_guc_on_begin(session, transaction, connection) -> None:
    """Re-apply ``app.user_id`` at the start of each transaction.

    After ``COMMIT``, SQLAlchemy may autobegin a new transaction for
    ``refresh()`` while the request context is still active. Re-setting the GUC
    keeps RLS policies working even if a pooled connection was reset.
    """
    user_id = user_id_ctx.get()
    if user_id is not None:
        connection.execute(
            sa.text("SELECT set_config('app.user_id', :user_id, false)"),
            {"user_id": str(user_id)},
        )


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        user_id = user_id_ctx.get()
        try:
            if user_id is not None:
                await apply_session_user_id(session, user_id)
            yield session
        finally:
            # Roll back any aborted/pending txn first so the RESET statements in
            # clear_tenant_session can run. Without this, an aborted transaction
            # makes RESET raise InFailedSQLTransactionError, masking the original
            # error. Safe no-op on success: services commit their own work and
            # get_db never commits.
            await session.rollback()
            await clear_tenant_session(session)
