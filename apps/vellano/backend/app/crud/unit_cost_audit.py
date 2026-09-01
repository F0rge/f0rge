from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unit_cost_audit import UnitCostAudit, UnitCostAuditSource
from f0rge_db.crud import BaseCRUD


class UnitCostAuditCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_for_sku(
        self,
        sku_id: uuid.UUID,
        location_id: Optional[uuid.UUID] = None,
    ) -> list[UnitCostAudit]:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(UnitCostAudit)
            .options(
                selectinload(UnitCostAudit.changed_by),
                selectinload(UnitCostAudit.location),
            )
            .where(UnitCostAudit.sku_id == sku_id)
            .order_by(UnitCostAudit.created_at.desc())
        )
        if location_id is not None:
            stmt = stmt.where(UnitCostAudit.location_id == location_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def latest_landed_costs_by_sku_ids(
        self,
        sku_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, Decimal]:
        if not sku_ids:
            return {}

        stmt = (
            select(UnitCostAudit.sku_id, UnitCostAudit.new_cost_zar)
            .where(
                UnitCostAudit.sku_id.in_(sku_ids),
                UnitCostAudit.source.in_([UnitCostAuditSource.LAND, UnitCostAuditSource.RECEIVE]),
            )
            .distinct(UnitCostAudit.sku_id)
            .order_by(UnitCostAudit.sku_id, UnitCostAudit.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
