from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp.prompts.workflows import register_workflow_prompts


def register_prompts(server: FastMCP) -> None:
    """Register MCP workflow prompts."""
    register_workflow_prompts(server)
