from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.purchase_order import PurchaseOrderResponse


from app.schemas.quantity import QuantityTotal


class ReorderItemResponse(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    reorder_min: int
    # The level a reorder brings stock back to; None reorders up to reorder_min.
    order_up_to: Optional[int] = None
    on_hand: QuantityTotal
    on_order: QuantityTotal
    # (order_up_to or reorder_min) - on_hand - on_order.
    need_qty: QuantityTotal
    # need_qty rounded up to the preferred supplier's pack_multiple, then raised to its
    # min_order_qty; equal to need_qty without a price row. Draft purchase orders use it.
    suggested_qty: QuantityTotal
    # From the SKU's price row for its preferred supplier; None without one.
    min_order_qty: Optional[int] = None
    pack_multiple: Optional[int] = None
    preferred_supplier_id: Optional[uuid.UUID] = None
    preferred_supplier_name: Optional[str] = None
    last_landed_cost_zar: Optional[Decimal] = None


class ReorderDraftPoCreate(BaseModel):
    sku_ids: list[uuid.UUID] = Field(min_length=1)


class ReorderDraftPoResponse(BaseModel):
    purchase_orders: list[PurchaseOrderResponse]
