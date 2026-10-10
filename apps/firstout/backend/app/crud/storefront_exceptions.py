from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from app.models.team import Team
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storefront_commerce_exception import (
    StorefrontCommerceException,
    StorefrontExceptionAlert,
    StorefrontExceptionAudit,
    StorefrontExceptionCommand,
    StorefrontExceptionProjection,
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
            stmt = stmt.execution_options(populate_existing=True).with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_seed_key(
        self, company_id: uuid.UUID, seed_key: str, *, for_update: bool = False
    ) -> Optional[StorefrontCommerceException]:
        stmt = select(StorefrontCommerceException).where(
            StorefrontCommerceException.company_id == company_id,
            StorefrontCommerceException.seed_key == seed_key,
        )
        if for_update:
            stmt = stmt.execution_options(populate_existing=True).with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_by_correlation(
        self, company_id: uuid.UUID, correlation_id: str
    ) -> list[StorefrontCommerceException]:
        result = await self.db.execute(
            select(StorefrontCommerceException).where(
                StorefrontCommerceException.company_id == company_id,
                StorefrontCommerceException.correlation_id == correlation_id,
            )
        )
        return list(result.scalars().all())

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

    async def lock_projection(
        self, company_id: uuid.UUID
    ) -> Optional[StorefrontExceptionProjection]:
        # Serialize the complete scan even before its first watermark exists.
        await self.db.execute(select(Team.id).where(Team.id == company_id).with_for_update())
        return await self.db.get(StorefrontExceptionProjection, company_id)

    async def list_live(self, company_id: uuid.UUID) -> list[StorefrontCommerceException]:
        result = await self.db.execute(
            select(StorefrontCommerceException)
            .where(
                StorefrontCommerceException.company_id == company_id,
                StorefrontCommerceException.source == "commerce",
            )
            .order_by(StorefrontCommerceException.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    async def pending_command(
        self, exception_id: uuid.UUID
    ) -> Optional[StorefrontExceptionCommand]:
        return await self.db.scalar(
            select(StorefrontExceptionCommand).where(
                StorefrontExceptionCommand.exception_id == exception_id,
                StorefrontExceptionCommand.status == "pending",
            )
        )

    async def add_command(self, command: StorefrontExceptionCommand) -> None:
        self.db.add(command)
        await self.db.flush()

    async def list_commands(
        self, company_id: uuid.UUID, limit: int
    ) -> list[tuple[StorefrontExceptionCommand, StorefrontCommerceException]]:
        result = await self.db.execute(
            select(StorefrontExceptionCommand, StorefrontCommerceException)
            .join(
                StorefrontCommerceException,
                StorefrontCommerceException.id == StorefrontExceptionCommand.exception_id,
            )
            .where(
                StorefrontExceptionCommand.company_id == company_id,
                StorefrontExceptionCommand.status == "pending",
            )
            .order_by(StorefrontExceptionCommand.created_at, StorefrontExceptionCommand.id)
            .limit(limit)
        )
        return [(command, row) for command, row in result.all()]

    async def get_command(
        self, command_id: uuid.UUID, company_id: uuid.UUID, *, for_update: bool = False
    ) -> Optional[StorefrontExceptionCommand]:
        stmt = (
            select(StorefrontExceptionCommand)
            .where(
                StorefrontExceptionCommand.id == command_id,
                StorefrontExceptionCommand.company_id == company_id,
            )
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return await self.db.scalar(stmt)

    async def get_projection(
        self, company_id: uuid.UUID
    ) -> Optional[StorefrontExceptionProjection]:
        return await self.db.scalar(
            select(StorefrontExceptionProjection)
            .where(StorefrontExceptionProjection.company_id == company_id)
            .execution_options(populate_existing=True)
        )

    async def get_audit(self, audit_id: uuid.UUID) -> Optional[StorefrontExceptionAudit]:
        return await self.db.get(StorefrontExceptionAudit, audit_id)
