from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp.resources.catalogs import register_catalog_resources
from app.mcp.resources.day_map import register_day_map_resources
from app.mcp.resources.dietary_catalog import register_dietary_catalog_resources
from app.mcp.resources.meal_guide import register_meal_guide_resources


def register_resources(server: FastMCP) -> None:
    """Register public MCP reference resources (no private schema dumps)."""
    register_catalog_resources(server)
    register_dietary_catalog_resources(server)
    register_day_map_resources(server)
    register_meal_guide_resources(server)
