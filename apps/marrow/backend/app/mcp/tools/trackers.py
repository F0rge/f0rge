from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import select

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _MAX_LIST_ROWS, _mcp_user_id, _validate_date
from app.models.tracker_log import TrackerLog
from app.services.trackers import TrackerService
from f0rge_db.tenant import owned_by_user


def register_trackers_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("list_trackers")
    async def list_trackers(active_only: bool = True, ctx: Context = None) -> dict[str, Any]:
        """List custom and seed tracker definitions.

        When active_only=True (default), archived trackers are excluded. Use
        get_tracker_logs for daily values; get_entry for legacy alcohol/caffeine
        columns mirrored from seed trackers.
        """
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            rows = await TrackerService(db).list_trackers(include_archived=not active_only)

        return {
            "trackers": [
                {
                    "id": r.id,
                    "name": r.name,
                    "kind": r.kind,
                    "icon": r.icon,
                    "unit": r.unit,
                    "position": r.position,
                    "archived": r.archived,
                    "is_seed": r.is_seed,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        }

    @server.tool()
    @instrument_tool("get_tracker_logs")
    async def get_tracker_logs(
        tracker_id: int,
        start_date: str,
        end_date: str,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Fetch tracker log values for one tracker in an inclusive date range.

        Capped at 200 rows. Returns empty logs when the tracker does not exist or
        has no values in range. Prefer get_entry for seed-tracker mirrors on a
        single day.
        """
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(TrackerLog)
                .where(
                    owned_by_user(TrackerLog.user_id),
                    TrackerLog.tracker_id == tracker_id,
                    TrackerLog.date >= start,
                    TrackerLog.date <= end,
                )
                .order_by(TrackerLog.date)
                .limit(_MAX_LIST_ROWS)
            )
            rows = (await db.execute(stmt)).scalars().all()

        return {
            "tracker_id": tracker_id,
            "logs": [
                {
                    "tracker_id": r.tracker_id,
                    "date": str(r.date),
                    "value": r.value,
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows
            ],
        }
