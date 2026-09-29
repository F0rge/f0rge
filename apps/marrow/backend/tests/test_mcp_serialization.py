from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp import tools as t_mod
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from tests.test_mcp_tools import _seed_entry, _seed_treatment


def _tool(server: FastMCP, name: str):
    return next(t for t in server._tool_manager.list_tools() if t.name == name).fn


async def _seed_day_with_meal(async_db: AsyncSession, date_str: str) -> None:
    entry = await _seed_entry(async_db, date_str)
    photo = Photo(entry_id=entry.id, label="MCP serialization meal", meal_time=None)
    async_db.add(photo)
    await async_db.flush()
    analysis = PhotoAnalysis(photo_id=photo.id, status="confirmed", dish_name="Oats")
    async_db.add(analysis)
    await async_db.flush()


def _mock_ro_session_expire_on_exit(async_db: AsyncSession):
    async def _aexit(*_args: object) -> bool:
        async_db.expire_all()
        return False

    return patch(
        "app.mcp.tools.scoped_ro_session",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=async_db),
            __aexit__=AsyncMock(side_effect=_aexit),
        ),
    )


@pytest.mark.asyncio
async def test_mcp_read_tools_json_dump_after_session_closes(async_db: AsyncSession) -> None:
    """Regression: tool handlers must not return lazy ORM state (DetachedInstanceError)."""
    await _seed_day_with_meal(async_db, "2026-09-29")
    await _seed_treatment(async_db, active=True)

    with _mock_ro_session_expire_on_exit(async_db):
        server = FastMCP("test")
        t_mod.register_tools(server)
        get_day = await _tool(server, "get_day")(date="2026-09-29")
        listed = await _tool(server, "list_days")(start_date="2026-09-01", end_date="2026-09-29")
        protocol = await _tool(server, "treatments")(on_date="2026-09-29")

    json.dumps(get_day)
    json.dumps(listed)
    json.dumps(protocol)


def test_list_tools_schema_succeeds() -> None:
    server = FastMCP("test")
    t_mod.register_tools(server)
    tools = server._tool_manager.list_tools()
    assert len(tools) == 19
    for registered in tools:
        assert registered.name
        assert registered.description
