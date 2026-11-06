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
    # Next overwrites both headers. A shared proxy secret prevents public API clients
    # from presenting an unsigned frontend origin; never trust X-Forwarded-Host.
    if forwarded is not None:
        supplied = request.headers.get("x-firstout-proxy-secret", "")
        if not settings.frontend_proxy_secret or not hmac.compare_digest(
            supplied, settings.frontend_proxy_secret
        ):
            raise HTTPException(400, "Untrusted frontend host")
        tenant_slug_from_host(direct, allow_local=not settings.cookie_secure)
        return tenant_slug_from_host(forwarded, allow_local=not settings.cookie_secure)
    if request.headers.get("x-forwarded-host"):
        raise HTTPException(400, "Untrusted forwarded host")
    return tenant_slug_from_host(direct, allow_local=not settings.cookie_secure)


def require_matching_host(slug: Optional[str], team_slug: str) -> None:
    if slug is not None and slug != team_slug:
        raise HTTPException(403, "Tenant host mismatch")
