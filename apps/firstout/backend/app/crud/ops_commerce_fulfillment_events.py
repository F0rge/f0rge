from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops_commerce_fulfillment_event import OpsCommerceFulfillmentEvent


class OpsCommerceFulfillmentEventsCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def pending_for_company(
        self, company_id: uuid.UUID, *, limit: int = 100
    ) -> list[OpsCommerceFulfillmentEvent]:
        result = await self.db.execute(
            select(OpsCommerceFulfillmentEvent)
            .where(
                OpsCommerceFulfillmentEvent.company_id == company_id,
                OpsCommerceFulfillmentEvent.acknowledged_at.is_(None),
            )
            .order_by(
                OpsCommerceFulfillmentEvent.occurred_at,
                OpsCommerceFulfillmentEvent.handoff_id,
                OpsCommerceFulfillmentEvent.revision,
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def acknowledge(
        self,
        company_id: uuid.UUID,
        event_ids: list[uuid.UUID],
    ) -> int:
        unique_ids = list(dict.fromkeys(event_ids))
        if not unique_ids:
            return 0
        result = await self.db.execute(
            select(OpsCommerceFulfillmentEvent).where(
                OpsCommerceFulfillmentEvent.company_id == company_id,
                OpsCommerceFulfillmentEvent.id.in_(unique_ids),
            )
        )
        rows = list(result.scalars().all())
        acknowledged_at = datetime.datetime.utcnow()
        for row in rows:
            if row.acknowledged_at is None:
                row.acknowledged_at = acknowledged_at
        return len(rows)
