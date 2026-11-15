from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.schemas.location_bin import BinOnHandResponse


from app.schemas.quantity import Quantity, QuantityTotal


class LocationStockResponse(BaseModel):
    location_id: uuid.UUID
    location_name: str
    on_hand: Quantity
    unit_cost_zar: Optional[Decimal] = None
    bins: list[BinOnHandResponse] = []


class InventorySkuResponse(BaseModel):
    is_archived: bool
    sku_id: uuid.UUID
    our_ref: str
    name: str
    on_order: Quantity
    on_hand: QuantityTotal
    sellable: bool
    unit_cost_zar: Optional[Decimal] = None
    locations: list[LocationStockResponse]
