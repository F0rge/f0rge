from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp.resources.catalogs import register_catalog_resources
from app.mcp.resources.day_map import register_day_map_resources


def register_resources(server: FastMCP) -> None:
    """Register public MCP reference resources (no private schema dumps)."""
    register_catalog_resources(server)
    register_day_map_resources(server)
