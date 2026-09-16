from __future__ import annotations

import asyncio
import sys

from app.config import settings
from app.platform.crud import TenantCRUD, TenantHostnameCRUD
from app.platform.database import platform_sessionmaker
from app.platform.models import Tenant, TenantHostname, TENANT_STATUS_READY
from app.platform.service import encrypt_database_url, normalise_hostname, validate_slug
from f0rge_db.crud import unit_of_work


class BootstrapError(Exception):
    pass


def _urls_collide() -> bool:
    platform = (settings.platform_database_url or "").strip()
    tenant = (settings.database_url or "").strip()
    if not platform:
        return True
    return platform == tenant


async def bootstrap_default_tenant() -> Tenant:
    if _urls_collide():
        raise BootstrapError(
            "Refusing to bootstrap: PLATFORM_DATABASE_URL is empty or equals DATABASE_URL"
        )
    slug = validate_slug(settings.default_tenant_slug)
    hostnames: list[str] = []
    seen: set[str] = set()
    for raw in list(settings.default_tenant_hostnames) + [f"{slug}.{settings.tenant_base_domain}"]:
        host = normalise_hostname(raw)
        if host not in seen:
            seen.add(host)
            hostnames.append(host)

    maker = platform_sessionmaker()
    async with maker() as db:
        crud = TenantCRUD(db)
        existing = await crud.get_by_slug(slug)
        async with unit_of_work(db):
            if existing is None:
                existing = Tenant(
                    slug=slug,
                    display_name=slug,
                    status=TENANT_STATUS_READY,
                    database_url_encrypted=encrypt_database_url(settings.database_url),
                    storage_prefix=settings.default_storage_user_id,
                    region="railway-sfo",
                )
                await crud.add_and_flush(existing)
            else:
                existing.display_name = slug
                existing.status = TENANT_STATUS_READY
                existing.database_url_encrypted = encrypt_database_url(settings.database_url)
                existing.storage_prefix = settings.default_storage_user_id
            host_crud = TenantHostnameCRUD(db)
            for index, host in enumerate(hostnames):
                row = await host_crud.get_by_hostname(host)
                if row is None:
                    await host_crud.add_and_flush(
                        TenantHostname(
                            hostname=host,
                            tenant_id=existing.id,
                            is_primary=index == 0,
                        )
                    )
                else:
                    row.tenant_id = existing.id
                    if index == 0:
                        row.is_primary = True
        reloaded = await crud.get_by_slug(slug)
        assert reloaded is not None
        return reloaded


def main() -> int:
    try:
        tenant = asyncio.run(bootstrap_default_tenant())
    except BootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    hosts = ", ".join(h.hostname for h in tenant.hostnames)
    print(f"tenant {tenant.slug} status={tenant.status} hostnames={hosts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
