"""Per-SKU stock figures shared by the catalogue table and the SKU overview.

"On order" has one definition here, the reorder one (``crud/reorder.py``): ``sku_stock.on_order``
(on-water and later stages) plus the quantity on open, non-archived purchase order lines.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import SkuStock
from app.models.layby import Layby, LaybyLine, LaybyStatus
from app.models.purchase_order import PoLine, PurchaseOrder, PurchaseOrderStatus
from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderStatus
from f0rge_db.organisation import tenant_id_ctx

# Purchase orders still to arrive, earliest stage first.
ARRIVING_STATUSES = (
    PurchaseOrderStatus.LANDED,
    PurchaseOrderStatus.ON_WATER,
    PurchaseOrderStatus.OPEN,
)


@dataclass(frozen=True)
class HeldDocument:
    kind: str  # "sales_order" | "layby"
    id: uuid.UUID
    number: str
    qty: Decimal


@dataclass(frozen=True)
class ArrivingOrder:
    id: uuid.UUID
    po_number: str
    status: str
    ordered_at: Optional[datetime.datetime]
    qty: Decimal


async def on_order_by_sku_id(
    db: AsyncSession, sku_ids: Optional[list[uuid.UUID]] = None
) -> dict[uuid.UUID, Decimal]:
    """Missing SKUs have nothing on order. ``None`` means every SKU of the tenant."""
    team_id = tenant_id_ctx.get()
    totals: dict[uuid.UUID, Decimal] = {}
    stock = select(SkuStock.sku_id, SkuStock.on_order).where(SkuStock.team_id == team_id)
    lines = (
        select(PoLine.sku_id, func.sum(PoLine.qty))
        .join(PurchaseOrder, PurchaseOrder.id == PoLine.po_id)
        .where(
            PoLine.team_id == team_id,
            PurchaseOrder.team_id == team_id,
            PurchaseOrder.status == PurchaseOrderStatus.OPEN,
            PurchaseOrder.is_archive.is_(False),
            PoLine.sku_id.is_not(None),
        )
        .group_by(PoLine.sku_id)
    )
    if sku_ids is not None:
        if not sku_ids:
            return {}
        stock = stock.where(SkuStock.sku_id.in_(sku_ids))
        lines = lines.where(PoLine.sku_id.in_(sku_ids))
    for statement in (stock, lines):
        for sku_id, qty in await db.execute(statement):
            totals[sku_id] = totals.get(sku_id, Decimal(0)) + Decimal(qty or 0)
    return totals


async def held_documents_by_sku_id(
    db: AsyncSession, sku_ids: Optional[list[uuid.UUID]] = None
) -> dict[uuid.UUID, list[HeldDocument]]:
    """Stock taken off the shelf for open sales orders and laybys holding stock (two queries).

    The one definition of "Held": the SKU overview lists these documents and the catalogue
    workspace sums them. ``None`` means every SKU of the tenant; missing SKUs hold nothing.
    """
    if sku_ids == []:
        return {}
    team_id = tenant_id_ctx.get()
    orders = (
        select(
            SalesOrderLine.sku_id,
            SalesOrder.id,
            SalesOrder.so_number,
            func.sum(SalesOrderLine.held_qty),
        )
        .join(SalesOrderLine, SalesOrderLine.sales_order_id == SalesOrder.id)
        .where(
            SalesOrder.team_id == team_id,
            SalesOrderLine.held_qty > 0,
            SalesOrder.status.in_((SalesOrderStatus.OPEN, SalesOrderStatus.AWAITING_STOCK)),
        )
        .group_by(SalesOrderLine.sku_id, SalesOrder.id, SalesOrder.so_number)
        .order_by(SalesOrder.so_number)
    )
    laybys = (
        select(LaybyLine.sku_id, Layby.id, Layby.layby_number, func.sum(LaybyLine.qty))
        .join(LaybyLine, LaybyLine.layby_id == Layby.id)
        .where(
            Layby.team_id == team_id,
            Layby.hold_stock.is_(True),
            Layby.status.in_((LaybyStatus.OPEN, LaybyStatus.READY)),
        )
        .group_by(LaybyLine.sku_id, Layby.id, Layby.layby_number)
        .order_by(Layby.layby_number)
    )
    if sku_ids is not None:
        orders = orders.where(SalesOrderLine.sku_id.in_(sku_ids))
        laybys = laybys.where(LaybyLine.sku_id.in_(sku_ids))
    found: dict[uuid.UUID, list[HeldDocument]] = {}
    for kind, statement in (("sales_order", orders), ("layby", laybys)):
        for sku_id, id_, number, qty in await db.execute(statement):
            found.setdefault(sku_id, []).append(HeldDocument(kind, id_, number, Decimal(qty)))
    return found


async def held_by_sku_id(
    db: AsyncSession, sku_ids: Optional[list[uuid.UUID]] = None
) -> dict[uuid.UUID, Decimal]:
    """Total Held per SKU, from ``held_documents_by_sku_id``."""
    return {
        sku_id: sum((doc.qty for doc in docs), Decimal(0))
        for sku_id, docs in (await held_documents_by_sku_id(db, sku_ids)).items()
    }


async def arriving_orders(db: AsyncSession, sku_id: uuid.UUID) -> list[ArrivingOrder]:
    """Non-archived purchase orders containing the SKU that have not been received."""
    team_id = tenant_id_ctx.get()
    rows = await db.execute(
        select(
            PurchaseOrder.id,
            PurchaseOrder.po_number,
            PurchaseOrder.status,
            PurchaseOrder.ordered_at,
            func.sum(PoLine.qty),
        )
        .join(PoLine, PoLine.po_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.team_id == team_id,
            PoLine.sku_id == sku_id,
            PurchaseOrder.is_archive.is_(False),
            PurchaseOrder.status.in_(ARRIVING_STATUSES),
        )
        .group_by(PurchaseOrder.id)
    )
    found = [
        ArrivingOrder(id_, number, status.value, ordered_at, Decimal(qty))
        for id_, number, status, ordered_at, qty in rows
    ]
    stage = {status.value: index for index, status in enumerate(ARRIVING_STATUSES)}
    found.sort(
        key=lambda row: (
            stage[row.status],
            row.ordered_at is None,
            row.ordered_at.timestamp() if row.ordered_at else 0.0,
            row.po_number,
        )
    )
    return found
