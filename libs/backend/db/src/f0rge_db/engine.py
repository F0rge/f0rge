from __future__ import annotations

from typing import AsyncIterator, Callable

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session

from f0rge_db.auth_context import user_id_ctx
from f0rge_db.db_url import asyncpg_connect_args, resolve_database_url
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session


def create_engine_and_sessionmaker(
    database_url: str,
    *,
    direct_database_url: str = "",
    echo: bool = False,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Build an AsyncEngine + async_sessionmaker from a raw (Fly/local) DATABASE_URL.

    Normalizes the URL for asyncpg (direct-host rewrite for pooled Fly MPG URLs)
    and disables the statement cache when stuck behind a transaction pooler.
    """
    kwargs: dict = {"echo": echo}
    connect_args = asyncpg_connect_args(database_url)
    if connect_args:
        kwargs["connect_args"] = connect_args
    engine = create_async_engine(
        resolve_database_url(database_url, direct_url=direct_database_url),
        **kwargs,
    )
    session_maker = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return engine, session_maker


_rls_hook_registered = False


def register_rls_hook() -> None:
    """Re-apply ``app.user_id`` at the start of each transaction (process-wide).

    After ``COMMIT``, SQLAlchemy may autobegin a new transaction for
    ``refresh()`` while the request context is still active. Re-setting the GUC
    keeps RLS policies working even if a pooled connection was reset.

    Listens on the ``Session`` class itself (all sessions in the process), same
    as the module-level ``@event.listens_for`` this replaces. Idempotent so
    repeated composition-module imports never double-register.
    """
    global _rls_hook_registered
    if _rls_hook_registered:
        return
    _rls_hook_registered = True

    @event.listens_for(Session, "after_begin")
    def _apply_tenant_guc_on_begin(session, transaction, connection) -> None:
        user_id = user_id_ctx.get()
        if user_id is not None:
            connection.execute(
                sa.text("SELECT set_config('app.user_id', :user_id, false)"),
                {"user_id": str(user_id)},
            )


def build_get_db(
    session_maker: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    """Build a FastAPI ``get_db`` dependency bound to ``session_maker``."""

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
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

    return get_db
