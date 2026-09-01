from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.reorder import ReorderCRUD, ReorderRow
from app.crud.supplier import SupplierCRUD
from app.crud.unit_cost_audit import UnitCostAuditCRUD
from app.schemas.purchase_order import PoLineCreate, PurchaseOrderCreate
from app.schemas.reorder import ReorderDraftPoCreate, ReorderDraftPoResponse, ReorderItemResponse
from app.services.purchase_orders import PurchaseOrderService
from f0rge_core.exceptions import ValidationError


class ReorderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = ReorderCRUD(db)
        self.supplier_crud = SupplierCRUD(db)
        self.unit_cost_audit_crud = UnitCostAuditCRUD(db)
        self.purchase_order_service = PurchaseOrderService(db)

    async def list(self) -> list[ReorderItemResponse]:
        rows = await self.crud.list_below_min()
        return await self._to_responses(rows)

    async def create_draft_pos(self, data: ReorderDraftPoCreate) -> ReorderDraftPoResponse:
        rows = await self.crud.list_below_min(sku_ids=data.sku_ids)
        by_sku_id = {row.sku_id: row for row in rows}

        for sku_id in data.sku_ids:
            row = by_sku_id.get(sku_id)
            if row is None:
                raise ValidationError("SKU is not on the reorder list")
            if row.preferred_supplier_id is None:
                raise ValidationError("Preferred supplier is required")

        landed_costs = await self.unit_cost_audit_crud.latest_landed_costs_by_sku_ids(
            list(data.sku_ids)
        )

        by_supplier: dict[uuid.UUID, list[ReorderRow]] = defaultdict(list)
        for sku_id in data.sku_ids:
            row = by_sku_id[sku_id]
            assert row.preferred_supplier_id is not None
            by_supplier[row.preferred_supplier_id].append(row)

        purchase_orders = []
        for supplier_id, supplier_rows in by_supplier.items():
            lines = [
                PoLineCreate(
                    sku_id=row.sku_id,
                    qty=row.suggested_qty,
                    factory_unit_amount=landed_costs.get(row.sku_id, Decimal("1")),
                )
                for row in supplier_rows
            ]
            po = await self.purchase_order_service.create(
                PurchaseOrderCreate(
                    supplier_id=supplier_id,
                    proforma_id=None,
                    lines=lines,
                )
            )
            purchase_orders.append(po)

        return ReorderDraftPoResponse(purchase_orders=purchase_orders)

    async def _to_responses(self, rows: list[ReorderRow]) -> list[ReorderItemResponse]:
        if not rows:
            return []

        sku_ids = [row.sku_id for row in rows]
        supplier_ids = [
            row.preferred_supplier_id for row in rows if row.preferred_supplier_id is not None
        ]
        landed_costs = await self.unit_cost_audit_crud.latest_landed_costs_by_sku_ids(sku_ids)
        supplier_names = await self.supplier_crud.names_by_ids(supplier_ids)

        return [
            ReorderItemResponse(
                sku_id=row.sku_id,
                our_ref=row.our_ref,
                name=row.name,
                reorder_min=row.reorder_min,
                on_hand=row.on_hand,
                on_order=row.on_order,
                suggested_qty=row.suggested_qty,
                preferred_supplier_id=row.preferred_supplier_id,
                preferred_supplier_name=(
                    supplier_names.get(row.preferred_supplier_id)
                    if row.preferred_supplier_id is not None
                    else None
                ),
                last_landed_cost_zar=landed_costs.get(row.sku_id),
            )
            for row in rows
        ]
