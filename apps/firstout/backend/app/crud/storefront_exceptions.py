from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storefront_commerce_exception import (
    StorefrontCommerceException,
    StorefrontExceptionAlert,
    StorefrontExceptionAudit,
)


class StorefrontExceptionCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_company(self, company_id: uuid.UUID) -> list[StorefrontCommerceException]:
        result = await self.db.execute(
            select(StorefrontCommerceException)
            .where(StorefrontCommerceException.company_id == company_id)
            .order_by(StorefrontCommerceException.detected_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, exception_id: uuid.UUID, *, for_update: bool = False
    ) -> Optional[StorefrontCommerceException]:
        stmt = select(StorefrontCommerceException).where(
            StorefrontCommerceException.id == exception_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_seed_key(
        self, company_id: uuid.UUID, seed_key: str
    ) -> Optional[StorefrontCommerceException]:
        return (
            await self.db.execute(
                select(StorefrontCommerceException).where(
                    StorefrontCommerceException.company_id == company_id,
                    StorefrontCommerceException.seed_key == seed_key,
                )
            )
        ).scalar_one_or_none()

    async def add(self, row: StorefrontCommerceException) -> StorefrontCommerceException:
        self.db.add(row)
        await self.db.flush()
        return row

    async def blocking_open(self, company_id: uuid.UUID) -> list[StorefrontCommerceException]:
        result = await self.db.execute(
            select(StorefrontCommerceException).where(
                StorefrontCommerceException.company_id == company_id,
                StorefrontCommerceException.blocks_checkout.is_(True),
                StorefrontCommerceException.status != "resolved",
            )
        )
        return list(result.scalars().all())

    async def audits_for(self, exception_id: uuid.UUID) -> list[StorefrontExceptionAudit]:
        result = await self.db.execute(
            select(StorefrontExceptionAudit)
            .where(StorefrontExceptionAudit.exception_id == exception_id)
            .order_by(StorefrontExceptionAudit.created_at.asc())
        )
        return list(result.scalars().all())

    async def audit_by_key(
        self, exception_id: uuid.UUID, idempotency_key: str
    ) -> Optional[StorefrontExceptionAudit]:
        return (
            await self.db.execute(
                select(StorefrontExceptionAudit).where(
                    StorefrontExceptionAudit.exception_id == exception_id,
                    StorefrontExceptionAudit.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()

    async def add_audit(self, row: StorefrontExceptionAudit) -> StorefrontExceptionAudit:
        self.db.add(row)
        await self.db.flush()
        return row

    async def add_alert(self, row: StorefrontExceptionAlert) -> StorefrontExceptionAlert:
        self.db.add(row)
        await self.db.flush()
        return row

    async def list_alerts(self, company_id: uuid.UUID) -> list[StorefrontExceptionAlert]:
        result = await self.db.execute(
            select(StorefrontExceptionAlert)
            .where(StorefrontExceptionAlert.company_id == company_id)
            .order_by(StorefrontExceptionAlert.created_at.desc())
        )
        return list(result.scalars().all())
