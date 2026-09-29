from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id, _validate_date
from app.services.trackers import TrackerService


def register_trackers_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("log_tracker")
    async def log_tracker(
        tracker_id: int,
        date: str,
        value: int,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Upsert a custom or seed tracker value for one calendar day."""
        parsed = _validate_date(date, "date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            log = await TrackerService(db).upsert_tracker_value(parsed, tracker_id, value)
            return {
                "tracker_id": log.tracker_id,
                "date": str(log.date),
                "value": log.value,
            }
