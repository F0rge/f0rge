"""Clerk identity verification. Local Firstout membership remains authoritative."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import asyncio
import jwt
from fastapi import HTTPException
from app.config import settings
from app.services.tenant_host import SLUG_PATTERN, RESERVED_SLUGS


@dataclass(frozen=True)
class ClerkSession:
    user_id: str
    org_id: str = ""
    org_slug: str = ""
    org_role: str = ""


@dataclass(frozen=True)
class ClerkIdentity:
    user_id: str
    org_id: str
    org_slug: str
    org_role: str


@lru_cache(maxsize=4)
def jwks_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        issuer.rstrip("/") + "/.well-known/jwks.json", cache_keys=True, lifespan=300, timeout=5
    )


async def verify_clerk_session(
    token: str, *, require_org: bool = False, require_active: bool = True
) -> ClerkSession:
    if (
        settings.tenant_isolation_mode != "enforced"
        or not settings.clerk_enabled
        or not settings.clerk_issuer.startswith("https://")
    ):
        raise HTTPException(401, "Clerk authentication unavailable")
    try:
        key = await asyncio.to_thread(
            jwks_client(settings.clerk_issuer).get_signing_key_from_jwt, token
        )
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"require": ["exp", "iat", "nbf", "iss", "sub"], "verify_aud": False},
            leeway=5,
        )
        if (require_org or require_active) and claims.get("sts") == "pending":
            raise ValueError("Active Clerk session required")
        org = claims.get("o") or {}
        if not isinstance(org, dict):
            raise ValueError("Invalid organisation claims")
        org_id = org.get("id") or claims.get("org_id") or claims.get("orgId")
        slug = org.get("slg") or claims.get("org_slug") or claims.get("orgSlug")
        role = org.get("rol") or claims.get("org_role") or ""
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise ValueError("Invalid subject")
        if require_org and not all(isinstance(value, str) and value for value in [org_id, slug]):
            raise ValueError("Active organisation required")
        if slug and (
            not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug) or slug in RESERVED_SLUGS
        ):
            raise ValueError("Invalid organisation slug")
        canonical_tenant_origin = f"https://{slug}.app.firstout.co.za" if slug else None
        authorized_party = claims.get("azp")
        if not settings.clerk_authorized_parties or not (
            authorized_party in settings.clerk_authorized_parties
            or (canonical_tenant_origin is not None and authorized_party == canonical_tenant_origin)
        ):
            raise ValueError("Unauthorized party")
        return ClerkSession(claims["sub"], org_id or "", slug or "", role)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(401, "Invalid Clerk session") from exc


async def verify_clerk_token(token: str) -> ClerkIdentity:
    session = await verify_clerk_session(token, require_org=True)
    return ClerkIdentity(session.user_id, session.org_id, session.org_slug, session.org_role)
