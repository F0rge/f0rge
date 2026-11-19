from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Annotated, Optional
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.crud.sku import SkuCRUD
from app.database import tenant_session
from app.permissions import STOCK_COST_VIEW
from app.services.clerk_api import ClerkAPI
from app.services.inventory import InventoryService
from app.services.mcp_tokens import McpTokenService, parse_credential
from app.services.permissions import PermissionService
from f0rge_core.exceptions import ConflictError, ExternalServiceError
from f0rge_db.crud import unit_of_work

MCP_PATH = "/mcp"
_MCP_SCOPE = "firstout:mcp"
_MAX_REQUEST_BYTES = 64 * 1024
_CLERK_TIMEOUT_SECONDS = 5


class McpAuthenticationUnavailableError(Exception):
    pass


class McpTokenVerifier:
    def __init__(self, provider: ClerkAPI) -> None:
        self.provider = provider

    async def verify_token(self, secret: str) -> Optional[AccessToken]:
        credential = parse_credential(secret)
        if credential is None:
            return None
        team_id, digest = credential
        async with tenant_session(team_id) as db:
            identity = await McpTokenService(db, team_id).clerk_identity_for_token(digest)
        if identity is None:
            return None
        if not self.provider.secret:
            raise McpAuthenticationUnavailableError()

        # Clerk may remove access while a legacy home grant remains in the directory.
        # Check the live provider outside the database transaction, then recheck local access.
        subject, organisation = identity
        try:
            async with asyncio.timeout(_CLERK_TIMEOUT_SECONDS):
                if not await self.provider.staff_access_active(subject, organisation):
                    return None
        except (ConflictError, ExternalServiceError, TimeoutError) as exc:
            raise McpAuthenticationUnavailableError() from exc
        async with tenant_session(team_id) as db, unit_of_work(db):
            token = await McpTokenService(db, team_id).authenticate(digest, identity)
            if token is None:
                return None
            return AccessToken(
                token=digest,
                client_id=str(token.id),
                subject=str(token.user_id),
                scopes=[_MCP_SCOPE],
                expires_at=int(token.expires_at.timestamp()),
                claims={
                    "team_id": str(team_id),
                    "clerk_subject": subject,
                    "clerk_organisation": organisation,
                },
            )


class McpAuthenticationAvailabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self.app(scope, receive, send)
        except McpAuthenticationUnavailableError:
            response = JSONResponse(
                {
                    "error": "temporarily_unavailable",
                    "error_description": "MCP authentication is unavailable",
                },
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)


class CatalogueSearchItem(BaseModel):
    id: uuid.UUID
    name: str
    sku: str
    category: Optional[str]
    unit_cost_zar: Optional[Decimal] = None


class CatalogueSearchPage(BaseModel):
    items: list[CatalogueSearchItem]
    total: int


async def catalogue_search(
    query: Annotated[str, Field(max_length=120, min_length=1)],
    limit: Annotated[int, Field(ge=1, le=25)] = 10,
    include_unit_cost: bool = False,
) -> CatalogueSearchPage:
    """Search active SKUs by name, SKU code, or barcode in the token's Firstout business."""
    query = query.strip()
    if not query:
        raise ToolError("Enter a name, SKU code, or barcode to search")
    access = get_access_token()
    if access is None or not access.claims:
        raise ToolError("Authentication required")

    team_id = uuid.UUID(access.claims["team_id"])
    identity = (access.claims["clerk_subject"], access.claims["clerk_organisation"])
    async with tenant_session(team_id) as db, unit_of_work(db):
        service = McpTokenService(db, team_id)
        # The transport and tool execute at separate boundaries. A token replaced,
        # revoked or disabled in between cannot read data using its previous authority.
        token = await service.authenticate(access.token, identity)
        if token is None:
            raise ToolError("This MCP token is no longer active")
        allowed = not include_unit_cost or await PermissionService(db).has_permission(
            token.user_id, STOCK_COST_VIEW
        )
        service.record(token, "catalogue_searched", "mcp", "success" if allowed else "denied")
        if allowed:
            skus, total = await SkuCRUD(db).list_filtered(q=query, limit=limit)
            costs = (
                await InventoryService(db).unit_costs_by_sku_id(
                    [sku.id for sku in skus], token.user_id
                )
                if include_unit_cost
                else {}
            )
            return CatalogueSearchPage(
                items=[
                    CatalogueSearchItem(
                        id=sku.id,
                        name=sku.name,
                        sku=sku.our_ref,
                        category=sku.category,
                        unit_cost_zar=costs.get(sku.id),
                    )
                    for sku in skus
                ],
                total=total,
            )
    raise ToolError("Unit costs require the stock cost viewing permission")


def create_mcp_app(provider: ClerkAPI) -> Starlette:
    url = str(settings.mcp_public_url)
    endpoint = urlsplit(url)
    server = MCPServer(
        "Firstout",
        token_verifier=McpTokenVerifier(provider),
        # These pre-issued personal tokens have no OAuth issuer to discover.
        auth=AuthSettings(issuer_url=url, resource_server_url=None, required_scopes=[_MCP_SCOPE]),
    )
    server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
        description=(
            "Search active SKUs by name, SKU code, or barcode. "
            "Unit costs are optional and require the Firstout stock cost viewing permission."
        ),
    )(catalogue_search)
    app = server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        max_request_body_size=_MAX_REQUEST_BYTES,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[endpoint.netloc],
            allowed_origins=[f"{endpoint.scheme}://{endpoint.netloc}", *settings.cors_origins],
        ),
    )
    app.add_middleware(McpAuthenticationAvailabilityMiddleware)
    return app


class McpEndpoint:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await scope["app"].state.firstout_mcp(scope, receive, send)
