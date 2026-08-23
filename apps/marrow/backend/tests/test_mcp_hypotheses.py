from __future__ import annotations

from unittest.mock import AsyncMock, patch

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hypothesis import Hypothesis


async def _seed_hypothesis(db: AsyncSession) -> Hypothesis:
    row = Hypothesis(
        slug="l1-sibo-imo",
        title="L1 SIBO/IMO",
        status="live",
        layer=1,
        kill_test="negative prepped H2/CH4 + no high-folate/low-B12",
        sort_order=10,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


def _tool(server: FastMCP, name: str):
    return next(t for t in server._tool_manager.list_tools() if t.name == name).fn


async def test_list_hypotheses_mcp(async_db: AsyncSession) -> None:
    await _seed_hypothesis(async_db)
    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool(server, "list_hypotheses")()

    assert len(result["hypotheses"]) == 1
    assert result["hypotheses"][0]["slug"] == "l1-sibo-imo"
    assert result["hypotheses"][0]["status"] == "live"


async def test_update_hypothesis_mcp_by_slug(async_db: AsyncSession) -> None:
    await _seed_hypothesis(async_db)
    from app.mcp import tools as t_mod

    with (
        patch("app.mcp.tools.scoped_ro_session") as mock_ro,
        patch("app.mcp.tools.scoped_main_session") as mock_main,
    ):
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_main.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_main.return_value.__aexit__ = AsyncMock(return_value=False)

        server = FastMCP("test")
        t_mod.register_tools(server)
        result = await _tool(server, "update_hypothesis")(
            slug="l1-sibo-imo",
            status="killed",
            last_evidence="negative breath test",
        )
        listed = await _tool(server, "list_hypotheses")()

    assert result["status"] == "killed"
    assert result["last_evidence"] == "negative breath test"
    assert result["kill_test"] == "negative prepped H2/CH4 + no high-folate/low-B12"
    assert listed["hypotheses"][0]["status"] == "killed"


async def test_n_of_1_mcp_round_trip(async_db: AsyncSession) -> None:
    from app.mcp import tools as t_mod

    with (
        patch("app.mcp.tools.scoped_ro_session") as mock_ro,
        patch("app.mcp.tools.scoped_main_session") as mock_main,
    ):
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_main.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_main.return_value.__aexit__ = AsyncMock(return_value=False)

        server = FastMCP("test")
        t_mod.register_tools(server)

        empty = await _tool(server, "get_n_of_1")()
        assert empty is None

        saved = await _tool(server, "update_n_of_1")(
            change="pause evening ibuprofen",
            start="2026-08-01",
            watch_field="bloating",
            stop_rule="14 days",
        )
        assert saved["change"] == "pause evening ibuprofen"
        fetched = await _tool(server, "get_n_of_1")()
        assert fetched is not None
        assert fetched["id"] == saved["id"]
