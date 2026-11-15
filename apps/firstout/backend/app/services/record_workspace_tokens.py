"""Short-lived snapshots are bound to a purpose, actor, tenant and resource."""

from __future__ import annotations

import time
import uuid
from typing import Optional

import jwt
from jwt import InvalidTokenError

from app.config import settings
from app.exceptions import ForbiddenError, RecordWorkspaceUnconfiguredError
from f0rge_core.exceptions import ConflictError
from f0rge_db.organisation import tenant_id_ctx


def signing_key() -> Optional[str]:
    if settings.record_workspace_signing_key:
        return settings.record_workspace_signing_key
    return settings.jwt_secret if len(settings.jwt_secret) >= 32 else None


def require_signing_key() -> str:
    key = signing_key()
    if key is None:
        raise RecordWorkspaceUnconfiguredError()
    return key


def issue_token(kind: str, resource: str, actor: uuid.UUID, payload: dict) -> str:
    return jwt.encode(
        {
            **payload,
            "kind": kind,
            "resource": resource,
            "actor": str(actor),
            "tenant": str(tenant_id_ctx.get()),
            "exp": int(time.time()) + 900,
        },
        require_signing_key(),
        algorithm="HS256",
    )


def read_token(token: str, kind: str, resource: str, actor: uuid.UUID) -> dict:
    key = require_signing_key()
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["HS256"],
            options={"require": ["exp", "kind", "resource", "actor", "tenant"]},
        )
    except InvalidTokenError as exc:
        raise ConflictError(
            "Selection expired or is invalid. Refresh the table and review again."
        ) from exc
    if (
        claims["kind"] != kind
        or claims["resource"] != resource
        or claims["actor"] != str(actor)
        or claims["tenant"] != str(tenant_id_ctx.get())
    ):
        raise ForbiddenError("This selection belongs to a different user or organisation")
    return claims
