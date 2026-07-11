from __future__ import annotations

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from app.config import settings
from app.mcp.auth import BearerTokenVerifier


def create_server() -> FastMCP:
    """Build the FastMCP server instance for the streamable-http transport.

    The BearerTokenVerifier gates every request.
    """
    # FastMCP refuses token_verifier without auth settings. We don't run an
    # OAuth flow — these URLs are metadata only, never resolved.
    base = AnyHttpUrl(f"http://{settings.mcp_server_host}:{settings.mcp_server_port}")
    return FastMCP(
        name="marrow",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        streamable_http_path="/mcp",
        token_verifier=BearerTokenVerifier(),
        auth=AuthSettings(issuer_url=base, resource_server_url=base),
    )
