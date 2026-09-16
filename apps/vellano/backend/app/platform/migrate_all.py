from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config

from app.config import settings
from app.platform.crud import TenantCRUD
from app.platform.database import platform_sessionmaker
from app.platform.service import decrypt_database_url

logger = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _upgrade_platform() -> None:
    cfg = Config(str(BACKEND_ROOT / "alembic_platform.ini"))
    if settings.platform_database_url:
        cfg.set_main_option("sqlalchemy.url", settings.platform_database_url)
    command.upgrade(cfg, "head")


def _upgrade_tenant(database_url: str) -> None:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


async def migrate_all(*, only: Optional[str] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not settings.platform_database_url:
        logger.info("PLATFORM_DATABASE_URL unset; migrating DATABASE_URL only")
        try:
            await asyncio.to_thread(_upgrade_tenant, settings.database_url)
        except Exception:
            logger.exception("tenant default migrate failed")
            return 1
        logger.info("tenant default ok")
        return 0

    failed = 0
    try:
        await asyncio.to_thread(_upgrade_platform)
        logger.info("platform ok")
    except Exception:
        logger.exception("platform migrate failed")
        return 1

    maker = platform_sessionmaker()
    async with maker() as db:
        tenants = await TenantCRUD(db).list_ready_and_provisioning()
    if only:
        tenants = [tenant for tenant in tenants if tenant.slug == only]
    for tenant in tenants:
        if not tenant.database_url_encrypted:
            logger.info("tenant %s skipped (no database url)", tenant.slug)
            failed += 1
            continue
        try:
            url = decrypt_database_url(tenant.database_url_encrypted)
            await asyncio.to_thread(_upgrade_tenant, url)
            logger.info("tenant %s ok", tenant.slug)
        except Exception:
            logger.exception("tenant %s migrate failed", tenant.slug)
            failed += 1
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade platform DB then every Tenant DB.")
    parser.add_argument("--only", default=None, help="Only this tenant slug")
    args = parser.parse_args()
    return asyncio.run(migrate_all(only=args.only))


if __name__ == "__main__":
    raise SystemExit(main())
