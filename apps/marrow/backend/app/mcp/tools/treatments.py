from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import select

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id
from app.models.treatment import Treatment
from f0rge_db.tenant import owned_by_user


def register_treatments_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("list_treatments")
    async def list_treatments(active_only: bool = True, ctx: Context = None) -> dict[str, Any]:
        """List treatments. When active_only=True, only treatments with no end_date are returned."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = select(Treatment).where(owned_by_user(Treatment.user_id))
            if active_only:
                stmt = stmt.where(Treatment.end_date.is_(None))
            stmt = stmt.order_by(Treatment.start_date.desc())
            rows = (await db.execute(stmt)).scalars().all()
        return {
            "treatments": [
                {
                    "id": r.id,
                    "name": r.name,
                    "group_name": r.group_name,
                    "type": r.type,
                    "start_date": str(r.start_date),
                    "end_date": str(r.end_date) if r.end_date else None,
                    "dose": r.dose,
                    "notes": r.notes,
                }
                for r in rows
            ]
        }
