from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import LocationStock, SkuStock
from app.models.purchase_order import PoLine, PurchaseOrder, PurchaseOrderStatus
from app.models.sku import Sku
from f0rge_db.crud import BaseCRUD


@dataclass(frozen=True)
class ReorderRow:
    sku_id: uuid.UUID
    our_ref: str
    name: str
    reorder_min: int
    on_hand: int
    on_order: int
    suggested_qty: int
    preferred_supplier_id: Optional[uuid.UUID]


class ReorderCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_below_min(self, sku_ids: Optional[list[uuid.UUID]] = None) -> list[ReorderRow]:
        on_hand_subq = (
            select(
                LocationStock.sku_id.label("sku_id"),
                func.coalesce(func.sum(LocationStock.on_hand), 0).label("on_hand"),
            )
            .group_by(LocationStock.sku_id)
            .subquery()
        )

        open_po_subq = (
            select(
                PoLine.sku_id.label("sku_id"),
                func.coalesce(func.sum(PoLine.qty), 0).label("open_po_qty"),
            )
            .join(PurchaseOrder, PurchaseOrder.id == PoLine.po_id)
            .where(PurchaseOrder.status == PurchaseOrderStatus.OPEN)
            .group_by(PoLine.sku_id)
            .subquery()
        )

        on_hand_col = func.coalesce(on_hand_subq.c.on_hand, 0)
        sku_on_order_col = func.coalesce(SkuStock.on_order, 0)
        open_po_col = func.coalesce(open_po_subq.c.open_po_qty, 0)
        on_order_col = sku_on_order_col + open_po_col
        total_col = on_hand_col + on_order_col

        stmt = (
            select(
                Sku.id,
                Sku.our_ref,
                Sku.name,
                Sku.reorder_min,
                Sku.preferred_supplier_id,
                on_hand_col.label("on_hand"),
                on_order_col.label("on_order"),
                (Sku.reorder_min - on_hand_col - on_order_col).label("suggested_qty"),
            )
            .outerjoin(on_hand_subq, on_hand_subq.c.sku_id == Sku.id)
            .outerjoin(SkuStock, SkuStock.sku_id == Sku.id)
            .outerjoin(open_po_subq, open_po_subq.c.sku_id == Sku.id)
            .where(Sku.reorder_min.isnot(None))
            .where(total_col < Sku.reorder_min)
            .order_by(Sku.our_ref)
        )
        if sku_ids is not None:
            stmt = stmt.where(Sku.id.in_(sku_ids))

        result = await self.db.execute(stmt)
        rows: list[ReorderRow] = []
        for row in result.all():
            rows.append(
                ReorderRow(
                    sku_id=row.id,
                    our_ref=row.our_ref,
                    name=row.name,
                    reorder_min=row.reorder_min,
                    on_hand=int(row.on_hand),
                    on_order=int(row.on_order),
                    suggested_qty=int(row.suggested_qty),
                    preferred_supplier_id=row.preferred_supplier_id,
                )
            )
        return rows
