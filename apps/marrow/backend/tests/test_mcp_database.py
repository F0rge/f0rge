from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp import tools as t_mod
from app.models.hypothesis import Hypothesis
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


def _tool(server: FastMCP, name: str):
    return next(t for t in server._tool_manager.list_tools() if t.name == name).fn


@pytest.mark.asyncio
async def test_hypotheses_mcp_uses_scoped_main_session(async_db: AsyncSession) -> None:
    """Hypotheses list/update run through scoped_main_session without DetachedInstanceError."""
    uid = uuid.UUID(settings.default_storage_user_id)
    await apply_session_user_id(async_db, uid)
    async_db.add(
        Hypothesis(
            slug="mcp-scoped-session-test",
            title="Scoped session test",
            status="live",
            layer=1,
            sort_order=99,
        )
    )
    await async_db.flush()

    with patch("app.mcp.database.make_main_session", return_value=async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        listed = await _tool(server, "hypotheses")()
        updated = await _tool(server, "update_hypothesis")(
            slug="mcp-scoped-session-test",
            last_evidence="scoped session regression",
        )

    slugs = {h["slug"] for h in listed["hypotheses"]}
    assert "mcp-scoped-session-test" in slugs
    assert updated["last_evidence"] == "scoped session regression"
