from __future__ import annotations

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from app.config import settings
from app.mcp.auth import BearerTokenVerifier
from app.mcp.prompts import register_prompts
from app.mcp.resources import register_resources
from app.mcp.tools import register_tools


def create_server() -> FastMCP:
    """Build the FastMCP server instance for the streamable-http transport.

    The BearerTokenVerifier gates every request. FastMCP requires AuthSettings
    whenever token_verifier is set; issuer_url is unused placeholder metadata.
    resource_server_url stays unset so we do not publish
    /.well-known/oauth-protected-resource — Cursor treats a 200 there as
    "use OAuth" and never sends the static Authorization header from mcp.json.
    """
    # FastMCP refuses token_verifier without auth settings. We don't run an
    # OAuth flow. issuer_url must be a syntactically valid URL; clients must
    # not be told it is a resource server (that mounts RFC 9728 discovery).
    issuer = AnyHttpUrl("https://mcp.marrow-health.com")
    return FastMCP(
        name="marrow",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        streamable_http_path="/mcp",
        token_verifier=BearerTokenVerifier(),
        auth=AuthSettings(issuer_url=issuer, resource_server_url=None),
    )


def register_all(server: FastMCP) -> None:
    """Register tools, resources, and prompts on the server."""
    register_tools(server)
    register_resources(server)
    register_prompts(server)
