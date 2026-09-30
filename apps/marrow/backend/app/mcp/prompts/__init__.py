from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_prompts(server: FastMCP) -> None:
    """Public Marrow MCP exposes tools and resources only — no prompts."""
