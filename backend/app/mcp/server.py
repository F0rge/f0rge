from __future__ import annotations

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from app.config import settings
from app.mcp.auth import BearerTokenVerifier


def create_server(*, transport: str = "stdio") -> FastMCP:
    """Build the FastMCP server instance.

    For stdio transport, no Bearer-token verifier is attached — the trust boundary
    is the shell session itself (SSH or docker exec).
    For streamable-http, the BearerTokenVerifier gates every request.
    """
    kwargs: dict = {
        "name": "health-tracker",
        "host": settings.mcp_server_host,
        "port": settings.mcp_server_port,
        "streamable_http_path": "/mcp",
    }
    if transport == "streamable-http":
        # FastMCP refuses token_verifier without auth settings. We don't run an
        # OAuth flow — these URLs are metadata only, never resolved.
        base = AnyHttpUrl(
            f"http://{settings.mcp_server_host}:{settings.mcp_server_port}"
        )
        kwargs["token_verifier"] = BearerTokenVerifier()
        kwargs["auth"] = AuthSettings(issuer_url=base, resource_server_url=base)

    return FastMCP(**kwargs)
