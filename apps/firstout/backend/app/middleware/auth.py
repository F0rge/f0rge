from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, Header, HTTPException
from app.services.clerk import verify_clerk_token
from app.services.staff_identity import staff_identity_ctx, resolve_membership
from app.services.tenant_host import request_tenant_slug, require_matching_host
from f0rge_db.organisation import tenant_id_ctx, apply_tenant_context
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from f0rge_db.auth_context import user_id_ctx
from app.crud.user import IdentityLookup
from app.database import get_db


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
    """Pure ASGI so streaming responses are not buffered by ``BaseHTTPMiddleware``."""

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


async def get_current_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None, include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    bearer = _bearer_token(authorization)
    if not bearer:
        raise HTTPException(401, "A Clerk sign-in is required")
    host_slug = request_tenant_slug(request)
    claims = await verify_clerk_token(bearer)
    user = await IdentityLookup(db).by_clerk_subject(claims.user_id)
    if user is None or user.is_disabled or user.role == "system":
        raise HTTPException(401, "Invalid session")
    identity = await resolve_membership(db, user, clerk_org_id=claims.org_id)
    if claims.org_slug != identity.team_slug:
        raise HTTPException(403, "Organisation slug mismatch")
    require_matching_host(host_slug, identity.team_slug)
    staff_identity_ctx.set(identity)
    user_id_ctx.set(identity.user_id)
    tenant_id_ctx.set(identity.team_id)
    await apply_tenant_context(db, identity.team_id)
    return identity.user_id
