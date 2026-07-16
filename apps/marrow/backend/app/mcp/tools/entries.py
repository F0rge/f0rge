from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import select

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import (
    _MAX_ENTRIES,
    _entry_to_dict,
    _mcp_user_id,
    _validate_date,
)
from app.models.entry import Entry
from f0rge_db.tenant import owned_by_user


def register_entries_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("get_entry")
    async def get_entry(date: str, ctx: Context = None) -> Optional[dict[str, Any]]:
        """Fetch one health log entry by ISO date (YYYY-MM-DD).

        Returns null if no entry exists for that date.
        """
        parsed = _validate_date(date, "date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            result = await db.execute(
                select(Entry).where(owned_by_user(Entry.user_id), Entry.date == parsed)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _entry_to_dict(row)

    @server.tool()
    @instrument_tool("list_entries")
    async def list_entries(start_date: str, end_date: str, ctx: Context = None) -> dict[str, Any]:
        """List health log entries in an inclusive date range (YYYY-MM-DD).

        Capped at 200 rows. Use a narrower range if you need more granularity.
        """
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(Entry)
                .where(
                    owned_by_user(Entry.user_id),
                    Entry.date >= start,
                    Entry.date <= end,
                )
                .order_by(Entry.date)
                .limit(_MAX_ENTRIES)
            )
            rows = (await db.execute(stmt)).scalars().all()
        return {"entries": [_entry_to_dict(r) for r in rows]}
