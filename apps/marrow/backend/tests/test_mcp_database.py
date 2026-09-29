from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.mcp.database import scoped_main_session, scoped_ro_session
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


@pytest.mark.asyncio
async def test_scoped_ro_session_hypotheses_round_trip(
    async_engine,
) -> None:
    """MCP hypotheses tools use real scoped sessions (not mocked) against Postgres."""
    from unittest.mock import patch

    from mcp.server.fastmcp import FastMCP

    from app.mcp import tools as t_mod

    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    session = maker()
    uid = uuid.UUID(settings.default_storage_user_id)
    await apply_session_user_id(session, uid)
    session.add(
        Hypothesis(
            slug="mcp-session-test",
            title="MCP session test",
            status="live",
            layer=1,
            sort_order=99,
        )
    )
    await session.commit()

    def _tool(server: FastMCP, name: str):
        return next(t for t in server._tool_manager.list_tools() if t.name == name).fn

    with patch("app.mcp.database.make_main_session", side_effect=lambda: maker()):
        server = FastMCP("test")
        t_mod.register_tools(server)
        listed = await _tool(server, "hypotheses")()
        updated = await _tool(server, "update_hypothesis")(
            slug="mcp-session-test",
            last_evidence="scoped session regression",
        )

    assert any(h["slug"] == "mcp-session-test" for h in listed["hypotheses"])
    assert updated["last_evidence"] == "scoped session regression"
    await session.close()
