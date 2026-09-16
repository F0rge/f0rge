from __future__ import annotations

import time
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.platform.crud import TenantCRUD
from app.platform.database import PlatformDatabaseUnconfiguredError, platform_sessionmaker
from app.platform.service import (
    decrypt_database_url,
    normalise_hostname,
    resolve_tenant_by_hostname,
)
from app.tenancy.errors import TenantContext, TenantMismatchError, TenantNotFoundError

_CACHE_TTL_SECONDS = 60.0
_hostname_cache: dict[str, tuple[float, TenantContext]] = {}


def hostname_from_request(request: Request) -> Optional[str]:
    raw = request.headers.get("x-tenant-host") or request.headers.get("X-Tenant-Host")
    if not raw:
        return None
    try:
        return normalise_hostname(raw)
    except Exception:
        raise TenantNotFoundError() from None


def _to_context(tenant) -> TenantContext:
    if not tenant.database_url_encrypted:
        raise TenantNotFoundError()
    return TenantContext(
        id=tenant.id,
        slug=tenant.slug,
        database_url=decrypt_database_url(tenant.database_url_encrypted),
        storage_prefix=tenant.storage_prefix,
    )


def _cached(hostname: str) -> Optional[TenantContext]:
    row = _hostname_cache.get(hostname)
    if row is None:
        return None
    expires, ctx = row
    if expires < time.monotonic():
        _hostname_cache.pop(hostname, None)
        return None
    return ctx


def invalidate_hostname_cache() -> None:
    _hostname_cache.clear()


async def resolve_tenant(
    request: Request,
    *,
    token_tid: Optional[uuid.UUID],
) -> TenantContext:
    hostname = hostname_from_request(request)
    try:
        maker = platform_sessionmaker()
    except PlatformDatabaseUnconfiguredError as exc:
        raise TenantNotFoundError() from exc

    async with maker() as db:
        return await _resolve(db, hostname=hostname, token_tid=token_tid)


async def _resolve(
    db: AsyncSession,
    *,
    hostname: Optional[str],
    token_tid: Optional[uuid.UUID],
) -> TenantContext:
    if token_tid is not None:
        tenant = await TenantCRUD(db).get_by_id(token_tid)
        if tenant is None or tenant.status != "ready":
            raise TenantNotFoundError()
        ctx = _to_context(tenant)
        if hostname is not None:
            mapped = await resolve_tenant_by_hostname(db, hostname)
            if mapped is None or mapped.id != ctx.id:
                raise TenantMismatchError()
        return ctx

    if hostname is None:
        raise TenantNotFoundError()

    cached = _cached(hostname)
    if cached is not None:
        return cached

    tenant = await resolve_tenant_by_hostname(db, hostname)
    if tenant is None:
        raise TenantNotFoundError()
    ctx = _to_context(tenant)
    _hostname_cache[hostname] = (time.monotonic() + _CACHE_TTL_SECONDS, ctx)
    return ctx


async def ready_context_for_slug(slug: str) -> Optional[TenantContext]:
    try:
        maker = platform_sessionmaker()
    except PlatformDatabaseUnconfiguredError:
        return None
    async with maker() as db:
        tenant = await TenantCRUD(db).get_by_slug(slug)
        if tenant is None or tenant.status != "ready":
            return None
        return _to_context(tenant)
