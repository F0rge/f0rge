from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp.resources.catalogs import register_catalog_resources
from app.mcp.resources.meta import register_meta_resources
from app.mcp.resources.schema import register_schema_resources


def register_resources(server: FastMCP) -> None:
    """Register all MCP resources (schema, catalogs, meta)."""
    register_schema_resources(server)
    register_catalog_resources(server)
    register_meta_resources(server)
