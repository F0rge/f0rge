"""Streamable HTTP MCP server for the buycycle tracker. Tailscale only; bearer token required."""

from __future__ import annotations

import os
from typing import Optional

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl

from buycycle_mcp.auth import BearerTokenVerifier, require_token
from buycycle_mcp import queries

INSTRUCTIONS = (
    "Read-only Buycycle deal finder (bikes and wheelsets). "
    "Net margin figures are estimates from the dashboard default fees and are labelled estimate. "
    "The server does not modify the tracker database."
)


def create_server() -> MCPServer:
    token = require_token()
    # issuer_url is unused placeholder metadata. resource_server_url stays unset so
    # the server does not advertise OAuth discovery; clients send the static bearer token.
    server = MCPServer(
        name="buycycle",
        instructions=INSTRUCTIONS,
        token_verifier=BearerTokenVerifier(token),
        auth=AuthSettings(issuer_url=AnyHttpUrl("http://127.0.0.1:8097"), resource_server_url=None),
    )
    register_tools(server)
    return server


def register_tools(server: MCPServer) -> None:
    server.add_tool(search_listings, structured_output=False)
    server.add_tool(get_listing, structured_output=False)
    server.add_tool(todays_deals, structured_output=False)
    server.add_tool(stats, structured_output=False)


def search_listings(
    kind: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    days_on_market_min: Optional[float] = None,
    days_on_market_max: Optional[float] = None,
    min_price_drop_percent: Optional[float] = None,
    min_net_margin: Optional[float] = None,
    brand: Optional[str] = None,
    size: Optional[str] = None,
    country: Optional[str] = None,
    sort: str = "net_margin",
    descending: bool = True,
    limit: int = 50,
) -> dict:
    """Search active listings.

    kind is bike or wheels. price_min and price_max are EUR. days_on_market_min and
    days_on_market_max are days listed. min_price_drop_percent is the drop from the
    original price. min_net_margin is estimated net profit in EUR after the dashboard
    default fees; every margin is labelled "estimate". brand, size, and country filter
    the row. sort is net_margin, price, days_on_market, price_drop_percent, or brand.
    limit is capped at 50.
    """
    return queries.search_listings(
        kind=kind,
        price_min=price_min,
        price_max=price_max,
        days_on_market_min=days_on_market_min,
        days_on_market_max=days_on_market_max,
        min_price_drop_percent=min_price_drop_percent,
        min_net_margin=min_net_margin,
        brand=brand,
        size=size,
        country=country,
        sort=sort,
        descending=descending,
        limit=limit,
    )


def get_listing(id: str) -> dict:
    """Listing details plus the full price history. Margins are labelled estimate."""
    return queries.get_listing(id)


def todays_deals() -> dict:
    """Today's new listings and price drops (Europe/Luxembourg), ranked by estimated net margin."""
    return queries.todays_deals()


def stats() -> dict:
    """Last tracker run, listing counts, and data freshness. Fee figures are estimates."""
    return queries.stats()


def http_app():
    """ASGI app: streamable HTTP at /mcp. host 0.0.0.0 keeps DNS-rebinding checks off."""
    host = os.environ.get("BUYCYCLE_MCP_HOST", "0.0.0.0")
    return create_server().streamable_http_app(streamable_http_path="/mcp", host=host)


def build_runtime() -> tuple:
    """Token-checked server plus the host and port used by `python -m buycycle_mcp`."""
    host = os.environ.get("BUYCYCLE_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("BUYCYCLE_MCP_PORT", "8097"))
    return create_server(), host, port
