"""Host validation is a consistency check, never an authentication mechanism."""

from __future__ import annotations

from typing import Optional

import hmac
import re
from fastapi import HTTPException, Request
from app.config import settings

RESERVED_SLUGS = frozenset(
    "www api app admin mail status support billing signup login static cdn trade".split()
)
SLUG_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
APEX_HOSTS = frozenset({"firstout.co.za", "www.firstout.co.za", "app.firstout.co.za"})


def validate_slug(slug: str) -> str:
    if not SLUG_PATTERN.fullmatch(slug) or slug in RESERVED_SLUGS:
        raise HTTPException(400, "Invalid tenant slug")
    return slug


def tenant_slug_from_host(host: str, *, allow_local: bool = False) -> Optional[str]:
    if allow_local and host in {
        "localhost:3003",
        "localhost:8003",
        "127.0.0.1:3003",
        "127.0.0.1:8003",
        "testserver",
        "test",
    }:
        return None
    if host in APEX_HOSTS or host == "api.firstout.co.za":
        return None
    suffix = ".app.firstout.co.za"
    if not host.endswith(suffix):
        raise HTTPException(400, "Invalid host")
    return validate_slug(host[: -len(suffix)])


def request_tenant_slug(request: Request) -> Optional[str]:
    direct = request.headers.get("host", "")
    forwarded = request.headers.get("x-firstout-frontend-host")
    direct_slug = tenant_slug_from_host(direct, allow_local=not settings.cookie_secure)
    slug = direct_slug
    if forwarded is not None and settings.frontend_proxy_secret:
        supplied = request.headers.get("x-firstout-proxy-signature", "")
        expected = hmac.digest(
            settings.frontend_proxy_secret.encode(), forwarded.encode(), "sha256"
        ).hex()
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(400, "Untrusted frontend host")
        slug = tenant_slug_from_host(forwarded, allow_local=not settings.cookie_secure)
    elif settings.tenant_isolation_mode == "enforced" and forwarded is not None:
        raise HTTPException(400, "Untrusted frontend host")
    elif request.headers.get("x-forwarded-host") and forwarded is None:
        raise HTTPException(400, "Untrusted forwarded host")
    # Without a secret the legacy Next header is ignored, never used to select a
    # tenant. Only the original home can be served before explicit cutover.
    if settings.tenant_isolation_mode == "single_home" and slug is not None:
        raise HTTPException(403, "Tenant hosts require enforced tenancy")
    return slug


def require_matching_host(slug: Optional[str], team_slug: str) -> None:
    if slug is not None and slug != team_slug:
        raise HTTPException(403, "Tenant host mismatch")
