from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated, Any, Optional
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.crud.sku import SkuCRUD
from app.crud.user import TeamCRUD, UserCRUD
from app.database import tenant_session
from app.exceptions import ForbiddenError
from app.middleware.auth import mcp_actor
from app.models.mcp_token import McpToken
from app.services.mcp_action_types import Action
from app.services.mcp_actions import ACTIONS, actions_index, search_actions
from app.services.mcp_operations import (
    begin_route_operation,
    execute_operation,
    finish_route_operation,
)
from app.services.mcp_route_runner import UNAVAILABLE, no_answer, run_route
from app.permissions import STOCK_COST_VIEW
from app.services.clerk_api import ClerkAPI
from app.services.inventory import InventoryService
from app.services.mcp_tokens import McpTokenService, parse_credential
from app.services.permissions import PermissionService
from app.services.staff_identity import resolve_membership, staff_identity_ctx
from f0rge_core.exceptions import ConflictError, DomainError, ExternalServiceError
from f0rge_db.auth_context import user_id_ctx
from f0rge_db.crud import unit_of_work

logger = logging.getLogger(__name__)

MCP_PATH = "/mcp"
ACTIONS_URI = "firstout://actions"
# The same for every caller. What a caller may use comes from find_actions and the index.
INSTRUCTIONS = (
    "Firstout is a furniture retailer's back office: catalogue, stock, warehouse, sales, till "
    "and books. Work in three steps. 1) find_actions with a task or a sidebar tab returns up "
    "to three actions you may use, each with its input schema; with no arguments it lists "
    "your domains. 2) run_read runs a read action. 3) run_write runs a write action "
    "immediately, as the token owner and under their Firstout permissions, so confirm "
    "intent with the user first. Give every intended change a fresh UUID request_id and "
    "reuse it only to retry that same change. If an outcome is uncertain, call run_read "
    "with action operations_lookup and that request_id before trying again with a new one. "
    f"The resource {ACTIONS_URI} lists every action you may use now, grouped by tab. "
    "Domains: Home, Till, Catalogue, Stock, Warehouse, Sales, Books, Admin. Access, "
    "identity, file uploads and document downloads stay in the Firstout app."
)
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


@asynccontextmanager
async def _staff_action():
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
        user = await UserCRUD(db).get_by_id(token.user_id)
        if user is None:
            raise ToolError("This staff account is no longer active")
        staff = await resolve_membership(db, user, clerk_org_id=identity[1])
        context = staff_identity_ctx.set(staff)
        actor = user_id_ctx.set(token.user_id)
        try:
            yield db, service, token
        finally:
            user_id_ctx.reset(actor)
            staff_identity_ctx.reset(context)


async def catalogue_search(
    query: Annotated[str, Field(max_length=120, min_length=1)],
    limit: Annotated[int, Field(ge=1, le=25)] = 10,
    include_unit_cost: bool = False,
) -> CatalogueSearchPage:
    """Search active SKUs by name, SKU code, or barcode in the token's Firstout business."""
    query = query.strip()
    if not query:
        raise ToolError("Enter a name, SKU code, or barcode to search")
    async with _staff_action() as (db, service, token):
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


async def find_actions(
    query: Annotated[str, Field(max_length=160)] = "",
    tab: Annotated[str, Field(max_length=80)] = "",
    offset: Annotated[int, Field(ge=0, le=10000)] = 0,
) -> dict[str, Any]:
    """List your domains, or find up to three permitted actions by task or sidebar tab. Page with next_offset."""
    async with _staff_action() as (db, service, token):
        granted = set(await PermissionService(db).keys_for_user(token.user_id))
        page = search_actions(query, tab, granted, offset)
        service.record(token, "actions_found", "mcp")
        return page


async def list_actions() -> str:
    """Every action your current permissions allow, by sidebar tab. No input schemas."""
    async with _staff_action() as (db, service, token):
        granted = set(await PermissionService(db).keys_for_user(token.user_id))
        service.record(token, "actions_found", "mcp")
        return actions_index(granted)


async def _run_route(
    action: Action, token: McpToken, args: BaseModel, body: Any, request_id: uuid.UUID | None
) -> dict[str, Any]:
    """Run a route action after its authorising transaction has committed.

    That transaction locked the token and team rows. The route works on its own connection
    and may need those rows, so nothing of ours stays open while it runs.
    """
    with mcp_actor(token.user_id, get_access_token().claims["clerk_organisation"]):
        outcome = await run_route(action.route, args, body)
    try:
        async with tenant_session(token.team_id) as db, unit_of_work(db):
            if request_id is not None:
                receipt = await finish_route_operation(db, token, request_id, outcome)
            else:
                McpTokenService(db, token.team_id).record(
                    token, "action_read", "mcp", outcome.audit, action_name=action.name
                )
    except Exception:
        # The route has answered. A started receipt already reports this as unknown.
        logger.exception("MCP could not record the outcome of %s", action.name)
        raise ToolError(no_answer(action.route)) from None
    if outcome.error is not None:
        raise ToolError(outcome.error)
    if request_id is None:
        return outcome.result
    # Only this first answer carries the route's response. A replay returns the receipt.
    if outcome.result is None:
        return {
            **receipt,
            "response_note": "The response was too large to return. Read the record.",
        }
    return {**receipt, "response": outcome.result}


async def _execute(
    action_name: str, arguments: dict, request_id: uuid.UUID | None
) -> dict[str, Any]:
    action = ACTIONS.get(action_name)
    writing = request_id is not None
    event = "write_requested" if writing else "action_read"
    async with _staff_action() as (db, service, token):
        if writing:
            # Staff directory changes take the conflicting lock; parallel writes share this one.
            await TeamCRUD(db).lock_current(shared=True)
        # Avoid signalling whether an inaccessible action exists.
        if action is None or not await PermissionService(db).current_member_has_any(
            token.user_id, action.permissions
        ):
            failure = UNAVAILABLE
            outcome = "denied"
        elif writing and not settings.mcp_writes_enabled:
            failure = "MCP writes are paused"
            outcome = "denied"
        elif writing != (action.effect != "read"):
            failure = "Use the runner matching the action's effect"
            outcome = "failed"
        else:
            try:
                args = action.arguments.model_validate(arguments)
                # Roll back partial business changes before committing a failure audit.
                async with db.begin_nested():
                    if action.route is not None:
                        replayed = writing and await begin_route_operation(
                            db, token, action, args, request_id
                        )
                        if replayed:
                            return replayed
                        failure = None
                    elif request_id is not None:
                        return await execute_operation(db, token, action, args, request_id)
                    else:
                        result = await action.handler(db, token, args)
                        service.record(token, event, "mcp", action_name=action.name)
                        return result
            except ValidationError as exc:
                # Include only schema locations and error codes, never input values.
                issues = exc.errors(include_input=False, include_url=False, include_context=False)
                failure = "Invalid arguments: " + ", ".join(
                    f"{'.'.join(str(part) for part in issue['loc'])} ({issue['type']})"
                    for issue in issues[:5]
                )
                outcome = "failed"
            except DomainError as exc:
                failure = exc.detail
                outcome = "denied" if isinstance(exc, ForbiddenError) else "failed"
        if failure is not None:
            service.record(
                token, event, "mcp", outcome, action_name=action.name if action else None
            )
    if failure is not None:
        raise ToolError(failure)
    # The client's own body is sent, as the app would send it. The route validates it again.
    return await _run_route(action, token, args, arguments.get("body"), request_id)


async def run_read(action: Annotated[str, Field(max_length=80)], arguments: dict) -> dict[str, Any]:
    """Run one read returned by find_actions, passing its named arguments."""
    return await _execute(action, arguments, None)


async def run_write(
    action: Annotated[str, Field(max_length=80)], arguments: dict, request_id: uuid.UUID
) -> dict[str, Any]:
    """Execute a discovered write immediately as the token owner. Use a new UUID for each intended change and reuse it on retry."""
    return await _execute(action, arguments, request_id)


def create_mcp_app(provider: ClerkAPI) -> Starlette:
    url = str(settings.mcp_public_url)
    endpoint = urlsplit(url)
    server = MCPServer(
        "Firstout",
        instructions=INSTRUCTIONS,
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
    for read_tool in (find_actions, run_read):
        server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))(read_tool)
    server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
        )
    )(run_write)
    server.resource(
        ACTIONS_URI,
        name="actions",
        title="Firstout actions",
        description="Every action your current permissions allow, grouped by sidebar tab.",
        mime_type="text/plain",
    )(list_actions)
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
