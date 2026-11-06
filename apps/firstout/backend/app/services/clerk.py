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


async def verify_clerk_token(token: str) -> ClerkIdentity:
    if not settings.clerk_enabled or not settings.clerk_issuer.startswith("https://"):
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
        org = claims.get("o") or {}
        if not isinstance(org, dict):
            raise ValueError("Invalid organisation claims")
        org_id = org.get("id") or claims.get("org_id") or claims.get("orgId")
        slug = org.get("slg") or claims.get("org_slug") or claims.get("orgSlug")
        role = org.get("rol") or claims.get("org_role") or ""
        if not all(isinstance(value, str) and value for value in [claims["sub"], org_id, slug]):
            raise ValueError("Active organisation required")
        valid_slug = bool(SLUG_PATTERN.fullmatch(slug)) and slug not in RESERVED_SLUGS
        if not valid_slug:
            raise ValueError("Invalid organisation slug")
        canonical_tenant_origin = f"https://{slug}.app.firstout.co.za"
        authorized_party = claims.get("azp")
        if not settings.clerk_authorized_parties or not (
            authorized_party in settings.clerk_authorized_parties
            or (canonical_tenant_origin is not None and authorized_party == canonical_tenant_origin)
        ):
            raise ValueError("Unauthorized party")
        return ClerkIdentity(claims["sub"], org_id, slug, role)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(401, "Invalid Clerk session") from exc
