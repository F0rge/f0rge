from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id
from app.services.social import SocialService


def register_people_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("list_people")
    async def list_people(ctx: Context = None) -> dict[str, Any]:
        """List accepted connections who can be tagged on meals."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            response = await SocialService(db).list_connections()
            return {
                "accepted": [
                    {
                        "connection_id": item.id,
                        "handle": item.user.handle,
                        "display_name": item.user.display_name,
                    }
                    for item in response.accepted
                ]
            }
