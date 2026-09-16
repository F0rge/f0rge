from __future__ import annotations

import uuid
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from f0rge_core.exceptions import UnauthorizedError

from app.services.auth import JWT_COOKIE_NAME, peek_token_tid
from app.tenancy.context import tenant_ctx
from app.tenancy.errors import TenantMismatchError, TenantNotFoundError
from app.tenancy.resolver import resolve_tenant

CUSTOMER_COOKIE_NAME = "vellano_customer_session"

EXEMPT_EXACT = frozenset({"/api/v1/health", "/docs", "/redoc", "/openapi.json"})
EXEMPT_PREFIXES = ("/api/v1/platform", "/api/v1/webhooks")


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_EXACT:
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in EXEMPT_PREFIXES)


def _tid_from_request(request: Request) -> Optional[uuid.UUID]:
    authorization = request.headers.get("Authorization")
    bearer = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    for token in (
        bearer,
        request.cookies.get(JWT_COOKIE_NAME),
        request.cookies.get(CUSTOMER_COOKIE_NAME),
    ):
        if not token:
            continue
        tid = peek_token_tid(token)
        if tid is not None:
            return tid
    return None


class TenantContextMiddleware:
    """Resolve Tenant from X-Tenant-Host / JWT tid. Fail closed with 404/401."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if _is_exempt(path):
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        token = tenant_ctx.set(None)
        try:
            ctx = await resolve_tenant(request, token_tid=_tid_from_request(request))
            tenant_ctx.set(ctx)
            await self.app(scope, receive, send)
        except TenantNotFoundError:
            response = JSONResponse({"detail": "tenant_not_found"}, status_code=404)
            await response(scope, receive, send)
        except (TenantMismatchError, UnauthorizedError):
            response = JSONResponse({"detail": "Invalid session"}, status_code=401)
            await response(scope, receive, send)
        finally:
            tenant_ctx.reset(token)
