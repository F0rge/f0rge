from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops_commerce_order import OpsCommerceOrder


class OpsCommerceOrdersCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_identity(
        self,
        company_id: uuid.UUID,
        channel: str,
        external_order_id: str,
        *,
        for_update: bool = False,
    ) -> Optional[OpsCommerceOrder]:
        stmt = select(OpsCommerceOrder).where(
            OpsCommerceOrder.company_id == company_id,
            OpsCommerceOrder.channel == channel,
            OpsCommerceOrder.external_order_id == external_order_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def payment_in_use(
        self,
        company_id: uuid.UUID,
        channel: str,
        external_payment_id: str,
    ) -> bool:
        return (
            await self.db.execute(
                select(OpsCommerceOrder.id).where(
                    OpsCommerceOrder.company_id == company_id,
                    OpsCommerceOrder.channel == channel,
                    OpsCommerceOrder.external_payment_id == external_payment_id,
                )
            )
        ).scalar_one_or_none() is not None

    async def get_by_id(
        self, handoff_id: uuid.UUID, *, for_update: bool = False
    ) -> Optional[OpsCommerceOrder]:
        stmt = select(OpsCommerceOrder).where(OpsCommerceOrder.id == handoff_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_sales_order(self, sales_order_id: uuid.UUID) -> Optional[OpsCommerceOrder]:
        # The paid payload is immutable; do not invert the handoff -> order lock order.
        return (
            await self.db.execute(
                select(OpsCommerceOrder).where(
                    OpsCommerceOrder.sales_order_id == sales_order_id,
                    OpsCommerceOrder.channel == "storefront",
                )
            )
        ).scalar_one_or_none()

    async def list_latest(
        self,
        company_id: uuid.UUID,
        limit: int = 100,
    ) -> list[OpsCommerceOrder]:
        result = await self.db.execute(
            select(OpsCommerceOrder)
            .where(OpsCommerceOrder.company_id == company_id)
            .order_by(OpsCommerceOrder.created_at.desc(), OpsCommerceOrder.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
