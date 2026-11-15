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
    on_hand: QuantityTotal
    on_order: QuantityTotal
    suggested_qty: QuantityTotal
    preferred_supplier_id: Optional[uuid.UUID] = None
    preferred_supplier_name: Optional[str] = None
    last_landed_cost_zar: Optional[Decimal] = None


class ReorderDraftPoCreate(BaseModel):
    sku_ids: list[uuid.UUID] = Field(min_length=1)


class ReorderDraftPoResponse(BaseModel):
    purchase_orders: list[PurchaseOrderResponse]
