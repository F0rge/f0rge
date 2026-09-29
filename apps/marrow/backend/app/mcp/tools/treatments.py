from __future__ import annotations

import datetime
from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id, _validate_date
from app.services.treatment_log import TreatmentLogService
from app.utils.dates import local_today


def register_treatments_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("treatments")
    async def treatments(
        on_date: Optional[str] = None,
        recent_days: int = 14,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Active treatment protocol for a day plus recent dose logs."""
        target = _validate_date(on_date, "on_date") if on_date else local_today()
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            service = TreatmentLogService(db)
            protocol = await service.get_protocol(target)
            start = target - datetime.timedelta(days=max(1, recent_days) - 1)
            active_ids = [item.id for item in protocol.items]
            logs = await service.crud.list_logs_in_range(active_ids, start, target)
            return {
                "on_date": str(target),
                "protocol": protocol.model_dump(),
                "recent_doses": [
                    {
                        "treatment_id": row.treatment_id,
                        "date": str(row.date),
                        "doses_taken": row.doses_taken,
                    }
                    for row in logs
                ],
            }

    @server.tool()
    @instrument_tool("log_dose")
    async def log_dose(
        treatment_id: int,
        date: str,
        doses_taken: int,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Log how many doses of a treatment were taken on a calendar day."""
        parsed = _validate_date(date, "date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            result = await TreatmentLogService(db).upsert(treatment_id, parsed, doses_taken)
            return {
                "treatment_id": treatment_id,
                "date": str(parsed),
                "doses_taken": result.log.doses_taken,
                "today": result.today.model_dump(),
            }
