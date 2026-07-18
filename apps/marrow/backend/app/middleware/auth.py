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


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Decode a valid JWT cookie (or bearer header) into the per-request user_id context."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        token = request.cookies.get(JWT_COOKIE_NAME) or _bearer_token(
            request.headers.get("Authorization")
        )
        token_ctx = user_id_ctx.set(None)
        try:
            if token:
                try:
                    user_id_ctx.set(decode_access_token(token))
                except Exception:
                    user_id_ctx.set(None)
            return await call_next(request)
        finally:
            user_id_ctx.reset(token_ctx)


async def get_current_user_id(
    ht_session: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None, include_in_schema=False),
) -> uuid.UUID:
    token = ht_session or _bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        user_id = decode_access_token(token)
        user_id_ctx.set(user_id)
        return user_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )


# Backward-compatible alias while routers migrate off session rows.
get_current_session = get_current_user_id
