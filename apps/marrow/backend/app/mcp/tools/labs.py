from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import func, select

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _MAX_LAB_HISTORY, _MAX_LABS, _mcp_user_id, _validate_date
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from f0rge_db.tenant import owned_by_user


def register_labs_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("get_lab_history")
    async def get_lab_history(marker_canonical_name: str, ctx: Context = None) -> dict[str, Any]:
        """Fetch all recorded values for a lab marker by its canonical name.

        Results ordered newest-first. Capped at 200 rows.
        """
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(
                    LabMarker.value,
                    LabMarker.unit,
                    LabMarker.flag,
                    Lab.lab_date.label("date"),
                )
                .join(Lab, LabMarker.lab_id == Lab.id)
                .where(
                    owned_by_user(LabMarker.user_id),
                    owned_by_user(Lab.user_id),
                    LabMarker.canonical_name == marker_canonical_name,
                )
                .order_by(Lab.lab_date.desc())
                .limit(_MAX_LAB_HISTORY)
            )
            rows = (await db.execute(stmt)).all()
        return {
            "marker": marker_canonical_name,
            "history": [
                {
                    "date": str(r.date),
                    "value": r.value,
                    "unit": r.unit,
                    "flag": r.flag,
                }
                for r in rows
            ],
        }

    @server.tool()
    @instrument_tool("list_labs")
    async def list_labs(start_date: str, end_date: str, ctx: Context = None) -> dict[str, Any]:
        """List lab uploads with marker counts in an inclusive date range.

        Capped at 200 rows.
        """
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(Lab, func.count(LabMarker.id).label("marker_count"))
                .outerjoin(LabMarker, LabMarker.lab_id == Lab.id)
                .where(
                    owned_by_user(Lab.user_id),
                    Lab.lab_date >= start,
                    Lab.lab_date <= end,
                )
                .group_by(Lab.id)
                .order_by(Lab.lab_date.desc())
                .limit(_MAX_LABS)
            )
            rows = (await db.execute(stmt)).all()
        return {
            "labs": [
                {
                    "id": r.Lab.id,
                    "date": str(r.Lab.lab_date),
                    "name": r.Lab.name,
                    "type": r.Lab.type,
                    "marker_count": r.marker_count,
                }
                for r in rows
            ]
        }
