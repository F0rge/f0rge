from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Cookie, Header, HTTPException, status
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from f0rge_db.auth_context import user_id_ctx
from app.services.auth import JWT_COOKIE_NAME, decode_access_token


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


def _resolve_user_id(
    cookie: Optional[str],
    authorization: Optional[str],
) -> Optional[uuid.UUID]:
    bearer = _bearer_token(authorization)
    for token in (bearer, cookie):
        if not token:
            continue
        try:
            return decode_access_token(token)
        except Exception:
            continue
    return None


class AuthContextMiddleware:
    """Pure ASGI so Nia SSE is not buffered by ``BaseHTTPMiddleware``."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        token_ctx = user_id_ctx.set(None)
        try:
            user_id_ctx.set(
                _resolve_user_id(
                    request.cookies.get(JWT_COOKIE_NAME),
                    request.headers.get("Authorization"),
                )
            )
            await self.app(scope, receive, send)
        finally:
            user_id_ctx.reset(token_ctx)


async def get_current_user_id(
    vellano_session: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None, include_in_schema=False),
) -> uuid.UUID:
    if not vellano_session and not _bearer_token(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = _resolve_user_id(vellano_session, authorization)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )
    user_id_ctx.set(user_id)
    return user_id
