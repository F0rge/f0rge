from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService
from app.services.playground_seed import PlaygroundSeedService
from app.services.role_user_seed import RoleUserSeedService
from app.services.roles import RoleSeedService
from app.services.till_seed import TillSeedService
from app.services.users import BootstrapService


async def seed_tenant_baseline(session: AsyncSession) -> None:
    """Roles, chart of accounts, till walk-in customer. No users or locations."""
    await RoleSeedService(session).seed()
    coa = ChartOfAccountsSeedService(session)
    await coa.seed_if_empty()
    await coa.ensure_opening_equity()
    await coa.ensure_customer_deposits()
    await coa.ensure_category_chart()
    await coa.ensure_bank_accounts()
    await TillSeedService(session).seed_if_empty()


async def seed_default_dev_extras(session: AsyncSession) -> None:
    """Vellano-only develop extras: owner, role users, locations, playground."""
    await BootstrapService(session).seed_if_empty()
    await LocationSeedService(session).seed_if_empty()
    await RoleUserSeedService(session).seed()
    await PlaygroundSeedService(session).seed_if_enabled()
