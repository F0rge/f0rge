from __future__ import annotations

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP

from app.mcp.database import scoped_main_session, scoped_ro_session
from app.mcp.tools._common import _mcp_user_id
from app.services.llm.factory import resolve_embedding_credentials

__all__ = [
    "_mcp_user_id",
    "get_access_token",
    "register_tools",
    "resolve_embedding_credentials",
    "scoped_main_session",
    "scoped_ro_session",
]


def register_tools(server: FastMCP) -> None:
    """Register all MCP tools onto the server instance."""
    from app.mcp.tools.entries import register_entries_tools
    from app.mcp.tools.food import register_food_tools
    from app.mcp.tools.hypotheses import register_hypotheses_tools
    from app.mcp.tools.labs import register_labs_tools
    from app.mcp.tools.metrics import register_metrics_tools
    from app.mcp.tools.search import register_search_tools
    from app.mcp.tools.sql import register_sql_tools
    from app.mcp.tools.trackers import register_trackers_tools
    from app.mcp.tools.treatments import register_treatments_tools
    from app.mcp.tools.weather import register_weather_tools

    register_search_tools(server)
    register_entries_tools(server)
    register_labs_tools(server)
    register_treatments_tools(server)
    register_hypotheses_tools(server)
    register_food_tools(server)
    register_trackers_tools(server)
    register_metrics_tools(server)
    register_weather_tools(server)
    register_sql_tools(server)
