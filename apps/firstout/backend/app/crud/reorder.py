from __future__ import annotations

import uuid
from decimal import ROUND_CEILING, Decimal
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import LocationStock, SkuStock
from app.models.purchase_order import PoLine, PurchaseOrder, PurchaseOrderStatus
from app.models.sku import Sku
from app.models.sku_supplier_price import SkuSupplierPrice
from f0rge_db.crud import BaseCRUD
from f0rge_db.organisation import current_tenant_id


@dataclass(frozen=True)
class ReorderRow:
    sku_id: uuid.UUID
    our_ref: str
    name: str
    reorder_min: int
    order_up_to: Optional[int]
    on_hand: Decimal
    on_order: Decimal
    # What brings stock back to order_up_to (or reorder_min).
    need_qty: Decimal
    # need_qty rounded for the preferred supplier's pack multiple and minimum order.
    suggested_qty: Decimal
    preferred_supplier_id: Optional[uuid.UUID]
    min_order_qty: Optional[int]
    pack_multiple: Optional[int]


def suggest_qty(
    need: Decimal, min_order_qty: Optional[int], pack_multiple: Optional[int]
) -> Decimal:
    """``need`` rounded up to the pack multiple, then raised to the minimum order (itself
    rounded up to the pack multiple). Without either, the need itself."""
    pack = Decimal(pack_multiple or 1)

    def up(qty: Decimal) -> Decimal:
        return (qty / pack).to_integral_value(rounding=ROUND_CEILING) * pack

    qty = up(need) if pack_multiple else need
    if min_order_qty:
        qty = max(qty, up(Decimal(min_order_qty)))
    return qty


def _below_reorder_min():
    """The reorder list's stock condition: a reorder minimum is set and on hand (every
    location, signed) plus on order is below it. Returns the on-hand and on-order columns and
    a function adding the joins and that condition to a ``select`` over ``Sku``.

    It describes stock level only; the reorder list also leaves out archived and
    do-not-reorder SKUs.
    """
    team_id = current_tenant_id()
    on_hand_subq = (
        select(
            LocationStock.sku_id.label("sku_id"),
            func.coalesce(func.sum(LocationStock.on_hand), 0).label("on_hand"),
        )
        .where(LocationStock.team_id == team_id)
        .group_by(LocationStock.sku_id)
        .subquery()
    )
    open_po_subq = (
        select(
            PoLine.sku_id.label("sku_id"),
            func.coalesce(func.sum(PoLine.qty), 0).label("open_po_qty"),
        )
        .join(PurchaseOrder, PurchaseOrder.id == PoLine.po_id)
        .where(
            PurchaseOrder.team_id == team_id,
            PoLine.team_id == team_id,
            PurchaseOrder.status == PurchaseOrderStatus.OPEN,
        )
        .where(PurchaseOrder.is_archive.is_(False))
        .where(PoLine.sku_id.isnot(None))
        .group_by(PoLine.sku_id)
        .subquery()
    )
    on_hand_col = func.coalesce(on_hand_subq.c.on_hand, 0)
    on_order_col = func.coalesce(SkuStock.on_order, 0) + func.coalesce(
        open_po_subq.c.open_po_qty, 0
    )

    def below_min(stmt: Select) -> Select:
        return (
            stmt.outerjoin(on_hand_subq, on_hand_subq.c.sku_id == Sku.id)
            .outerjoin(SkuStock, (SkuStock.sku_id == Sku.id) & (SkuStock.team_id == team_id))
            .outerjoin(open_po_subq, open_po_subq.c.sku_id == Sku.id)
            .where(Sku.team_id == team_id, Sku.reorder_min.isnot(None))
            .where(on_hand_col + on_order_col < Sku.reorder_min)
        )

    return on_hand_col, on_order_col, below_min


class ReorderCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_below_min(
        self,
        sku_ids: Optional[list[uuid.UUID]] = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ReorderRow]:
        on_hand_col, on_order_col, below_min = _below_reorder_min()
        stmt = (
            select(
                Sku.id,
                Sku.our_ref,
                Sku.name,
                Sku.reorder_min,
                Sku.order_up_to,
                Sku.preferred_supplier_id,
                SkuSupplierPrice.min_order_qty,
                SkuSupplierPrice.pack_multiple,
                on_hand_col.label("on_hand"),
                on_order_col.label("on_order"),
                (
                    func.coalesce(Sku.order_up_to, Sku.reorder_min) - on_hand_col - on_order_col
                ).label("need_qty"),
            )
            .outerjoin(
                SkuSupplierPrice,
                (SkuSupplierPrice.sku_id == Sku.id)
                & (SkuSupplierPrice.supplier_id == Sku.preferred_supplier_id)
                & (SkuSupplierPrice.team_id == current_tenant_id()),
            )
            .where(Sku.is_archived.is_(False), Sku.do_not_reorder.is_(False))
            .order_by(Sku.our_ref)
        )
        stmt = below_min(stmt)
        if sku_ids is not None:
            stmt = stmt.where(Sku.id.in_(sku_ids))

        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        rows: list[ReorderRow] = []
        for row in result.all():
            rows.append(
                ReorderRow(
                    sku_id=row.id,
                    our_ref=row.our_ref,
                    name=row.name,
                    reorder_min=row.reorder_min,
                    order_up_to=row.order_up_to,
                    on_hand=Decimal(row.on_hand),
                    on_order=Decimal(row.on_order),
                    need_qty=Decimal(row.need_qty),
                    suggested_qty=suggest_qty(
                        Decimal(row.need_qty), row.min_order_qty, row.pack_multiple
                    ),
                    preferred_supplier_id=row.preferred_supplier_id,
                    min_order_qty=row.min_order_qty,
                    pack_multiple=row.pack_multiple,
                )
            )
        return rows


async def below_reorder_min_sku_ids(
    db: AsyncSession, sku_ids: Optional[list[uuid.UUID]] = None
) -> set[uuid.UUID]:
    """SKUs meeting the reorder list's stock condition, archived and do-not-reorder included.
    ``None`` means every SKU of the tenant. One query."""
    if sku_ids == []:
        return set()
    _, _, below_min = _below_reorder_min()
    stmt = below_min(select(Sku.id))
    if sku_ids is not None:
        stmt = stmt.where(Sku.id.in_(sku_ids))
    return set((await db.execute(stmt)).scalars())
