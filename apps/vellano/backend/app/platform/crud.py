from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.platform.models import Signup, Tenant, TenantHostname, TENANT_STATUS_READY
from f0rge_db.crud import BaseCRUD


class TenantCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, tenant_id: uuid.UUID) -> Optional[Tenant]:
        return (
            await self.db.execute(
                select(Tenant).options(selectinload(Tenant.hostnames)).where(Tenant.id == tenant_id)
            )
        ).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        return (
            await self.db.execute(
                select(Tenant).options(selectinload(Tenant.hostnames)).where(Tenant.slug == slug)
            )
        ).scalar_one_or_none()

    async def list_ready(self) -> list[Tenant]:
        result = await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.hostnames))
            .where(Tenant.status == TENANT_STATUS_READY)
        )
        return list(result.scalars().all())

    async def list_ready_and_provisioning(self) -> list[Tenant]:
        result = await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.hostnames))
            .where(Tenant.status.in_(("ready", "provisioning")))
        )
        return list(result.scalars().all())


class TenantHostnameCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_hostname(self, hostname: str) -> Optional[TenantHostname]:
        return (
            await self.db.execute(
                select(TenantHostname)
                .options(selectinload(TenantHostname.tenant))
                .where(TenantHostname.hostname == hostname)
            )
        ).scalar_one_or_none()


class SignupCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, signup_id: uuid.UUID) -> Optional[Signup]:
        return (
            await self.db.execute(select(Signup).where(Signup.id == signup_id))
        ).scalar_one_or_none()

    async def get_by_verify_token_hash(self, token_hash: str) -> Optional[Signup]:
        return (
            await self.db.execute(select(Signup).where(Signup.verify_token_hash == token_hash))
        ).scalar_one_or_none()
