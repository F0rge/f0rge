from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.unit_cost_audit import UnitCostAudit
from f0rge_db.crud import BaseCRUD


class UnitCostAuditCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_for_sku(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
    ) -> list[UnitCostAudit]:
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
