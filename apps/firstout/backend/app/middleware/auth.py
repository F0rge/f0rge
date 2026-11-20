from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Optional

from fastapi import Depends, Header, HTTPException
from app.services.clerk import verify_clerk_token
from app.services.staff_identity import StaffIdentity, staff_identity_ctx, resolve_membership
from app.services.tenant_host import request_tenant_slug, require_matching_host
from f0rge_db.organisation import tenant_id_ctx, apply_tenant_context
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from f0rge_db.auth_context import user_id_ctx
from app.crud.user import IdentityLookup
from app.database import get_db
from app.models.user import User


@dataclass(frozen=True)
class McpActor:
    """A staff member the MCP server has already authenticated, acting in-process."""

    user_id: uuid.UUID
    clerk_org_id: str
    # The token's business. The membership resolved from the organisation must match it.
    team_id: uuid.UUID

    def __post_init__(self) -> None:
        # An empty organisation would make resolve_membership fall back to the legacy
        # home grant instead of the organisation the MCP token was verified against.
        if (
            not isinstance(self.user_id, uuid.UUID)
            or not isinstance(self.team_id, uuid.UUID)
            or not self.clerk_org_id
        ):
            raise ValueError("An MCP actor needs a user ID, a Clerk organisation ID and a team ID")


# Task-local and settable only by code in this process: no header, cookie, body or ASGI
# scope value reaches it. A value set inside one MCP tool call is visible to that task and
# the tasks it starts, never to another request. Set it only through ``mcp_actor``.
mcp_actor_ctx: ContextVar[Optional[McpActor]] = ContextVar("mcp_actor", default=None)


@contextmanager
def mcp_actor(user_id: uuid.UUID, clerk_org_id: str, team_id: uuid.UUID) -> Iterator[None]:
    """Run in-process API requests as this staff member; always restores the previous value."""
    token = mcp_actor_ctx.set(McpActor(user_id, clerk_org_id, team_id))
    try:
        yield
    finally:
        mcp_actor_ctx.reset(token)


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization:
        scheme, separator, token = authorization.partition(" ")
        if (
            separator
            and scheme.lower() == "bearer"
            and token
            and not any(char.isspace() for char in token)
        ):
            return token
    return None


class AuthContextMiddleware:
    """Pure ASGI so streaming responses are not buffered by ``BaseHTTPMiddleware``.

    ``mcp_actor_ctx`` is deliberately not reset here. The in-process MCP request passes
    through this middleware in its caller's task, so clearing it would disable the seam.
    An external request never has it set: its task starts from the server's context.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token_ctx = user_id_ctx.set(None)
        tenant_token = tenant_id_ctx.set(None)
        identity_token = staff_identity_ctx.set(None)
        try:
            await self.app(scope, receive, send)
        finally:
            user_id_ctx.reset(token_ctx)
            tenant_id_ctx.reset(tenant_token)
            staff_identity_ctx.reset(identity_token)


async def _staff_identity(
    db: AsyncSession, user: Optional[User], clerk_org_id: Optional[str]
) -> StaffIdentity:
    if user is None or user.is_disabled or user.role == "system":
        raise HTTPException(401, "Invalid session")
    return await resolve_membership(db, user, clerk_org_id=clerk_org_id)


async def _enter_staff_context(db: AsyncSession, identity: StaffIdentity) -> uuid.UUID:
    staff_identity_ctx.set(identity)
    user_id_ctx.set(identity.user_id)
    tenant_id_ctx.set(identity.team_id)
    await apply_tenant_context(db, identity.team_id)
    return identity.user_id


async def get_current_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None, include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    actor = mcp_actor_ctx.get()
    if actor is not None:
        # In-process MCP call: identity comes only from the context variable, never from
        # the request. The user, membership and team are re-read on every call. There is
        # no external host to compare, so the tenant-host consistency check does not apply.
        if authorization is not None:
            # Two identities on one request is a caller bug; refuse instead of choosing.
            raise HTTPException(401, "Invalid session")
        user = await IdentityLookup(db).by_session_subject(actor.user_id)
        identity = await _staff_identity(db, user, actor.clerk_org_id)
        if identity.team_id != actor.team_id:
            # The organisation now resolves to another business than the token's.
            raise HTTPException(401, "Invalid session")
        return await _enter_staff_context(db, identity)
    bearer = _bearer_token(authorization)
    if not bearer:
        raise HTTPException(401, "A Clerk sign-in is required")
    host_slug = request_tenant_slug(request)
    claims = await verify_clerk_token(bearer)
    user = await IdentityLookup(db).by_clerk_subject(claims.user_id)
    identity = await _staff_identity(db, user, claims.org_id)
    if claims.org_slug != identity.team_slug:
        raise HTTPException(403, "Organisation slug mismatch")
    require_matching_host(host_slug, identity.team_slug)
    return await _enter_staff_context(db, identity)
