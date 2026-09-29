from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.mcp.database import scoped_main_session
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session


@pytest.mark.asyncio
async def test_rollback_before_clear_tenant_after_failed_sql(async_db: AsyncSession) -> None:
    """Regression: aborted transactions must not make RESET raise InFailedSQLTransactionError."""
    uid = uuid.UUID(settings.default_storage_user_id)
    await apply_session_user_id(async_db, uid)
    with pytest.raises(sa.exc.ProgrammingError):
        await async_db.execute(sa.text("SELECT * FROM no_such_mcp_cleanup_table"))
    await async_db.rollback()
    await clear_tenant_session(async_db)


@pytest.mark.asyncio
async def test_scoped_main_session_cleanup_after_failed_sql(async_engine) -> None:
    """MCP scoped_main_session rolls back before RESET (matches FastAPI get_db)."""
    uid = uuid.UUID(settings.default_storage_user_id)
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    with patch("app.mcp.database.make_main_session", side_effect=lambda: maker()):
        with pytest.raises(sa.exc.ProgrammingError):
            async with scoped_main_session(uid) as db:
                await db.execute(sa.text("SELECT * FROM no_such_mcp_cleanup_table_xyz"))
