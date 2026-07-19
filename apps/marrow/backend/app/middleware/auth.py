from __future__ import annotations

import uuid

from fastapi import Cookie, Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from f0rge_db.auth_context import user_id_ctx
from app.services.auth import JWT_COOKIE_NAME, decode_access_token


def _bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


def _resolve_user_id(
    cookie: str | None,
    authorization: str | None,
) -> uuid.UUID | None:
    """Decode the first valid credential; try bearer when cookie JWT is stale."""
    bearer = _bearer_token(authorization)
    for token in (cookie, bearer):
        if not token:
            continue
        try:
            return decode_access_token(token)
        except Exception:
            continue
    return None


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Decode a valid JWT cookie (or bearer header) into the per-request user_id context."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        token_ctx = user_id_ctx.set(None)
        try:
            user_id_ctx.set(
                _resolve_user_id(
                    request.cookies.get(JWT_COOKIE_NAME),
                    request.headers.get("Authorization"),
                )
            )
            return await call_next(request)
        finally:
            user_id_ctx.reset(token_ctx)


async def get_current_user_id(
    ht_session: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None, include_in_schema=False),
) -> uuid.UUID:
    if not ht_session and not _bearer_token(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = _resolve_user_id(ht_session, authorization)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )
    user_id_ctx.set(user_id)
    return user_id


# Backward-compatible alias while routers migrate off session rows.
get_current_session = get_current_user_id
