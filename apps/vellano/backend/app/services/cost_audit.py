from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.unit_cost_audit import UnitCostAuditCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.user import UserCRUD
from app.models.unit_cost_audit import UnitCostAudit, UnitCostAuditSource
from app.schemas.cost_audit import UnitCostAuditResponse, UnitCostCorrectionRequest
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class CostAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UnitCostAuditCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.user_crud = UserCRUD(db)

    async def record(
        self,
        *,
        sku_id: uuid.UUID,
        new_cost_zar: Decimal,
        changed_by_user_id: uuid.UUID,
        source: UnitCostAuditSource,
        old_cost_zar: Optional[Decimal] = None,
        location_id: Optional[uuid.UUID] = None,
        po_id: Optional[uuid.UUID] = None,
        po_line_id: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
    ) -> UnitCostAudit:
        entry = UnitCostAudit(
            sku_id=sku_id,
            location_id=location_id,
            po_id=po_id,
            po_line_id=po_line_id,
            old_cost_zar=old_cost_zar,
            new_cost_zar=new_cost_zar,
            changed_by_user_id=changed_by_user_id,
            source=source,
            note=note,
        )
        await self.crud.add_and_flush(entry)
        return entry

    async def list_for_sku(
        self,
        sku_id: uuid.UUID,
        location_id: Optional[uuid.UUID] = None,
    ) -> list[UnitCostAuditResponse]:
        rows = await self.crud.list_for_sku(sku_id, location_id)
        return [self._to_response(row) for row in rows]

    async def correct_unit_cost(
        self,
        sku_id: uuid.UUID,
        user_id: uuid.UUID,
        data: UnitCostCorrectionRequest,
    ) -> UnitCostAuditResponse:
        if data.unit_cost_zar <= 0:
            raise ValidationError("unit_cost_zar must be positive")

        loc_stock = await self.location_stock_crud.get_by_sku_and_location(
            sku_id,
            data.location_id,
        )
        if loc_stock is None or loc_stock.on_hand <= 0:
            raise NotFoundError("No on-hand stock at this location for the SKU")

        old_cost = loc_stock.unit_cost_zar

        async with unit_of_work(self.db):
            loc_stock.unit_cost_zar = data.unit_cost_zar
            entry = await self.record(
                sku_id=sku_id,
                location_id=data.location_id,
                old_cost_zar=old_cost,
                new_cost_zar=data.unit_cost_zar,
                changed_by_user_id=user_id,
                source=UnitCostAuditSource.CORRECTION,
                note="Manual unit cost correction",
            )

        reloaded = await self.crud.list_for_sku(sku_id, data.location_id)
        for row in reloaded:
            if row.id == entry.id:
                return self._to_response(row)
        return self._to_response(entry)

    @staticmethod
    def _to_response(row: UnitCostAudit) -> UnitCostAuditResponse:
        location_name = row.location.name if row.location is not None else None
        changed_by = row.changed_by
        return UnitCostAuditResponse(
            id=row.id,
            sku_id=row.sku_id,
            location_id=row.location_id,
            location_name=location_name,
            po_id=row.po_id,
            old_cost_zar=row.old_cost_zar,
            new_cost_zar=row.new_cost_zar,
            changed_by_user_id=row.changed_by_user_id,
            changed_by_email=changed_by.email,
            changed_by_display_name=changed_by.display_name,
            source=row.source.value,
            created_at=row.created_at,
            note=row.note,
        )
