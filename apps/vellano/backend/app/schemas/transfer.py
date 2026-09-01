from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class TransferCreate(BaseModel):
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    from_bin_id: Optional[uuid.UUID] = None
    to_bin_id: Optional[uuid.UUID] = None


class TransferLocationStock(BaseModel):
    location_id: uuid.UUID
    location_name: str
    on_hand: int
    unit_cost_zar: Optional[Decimal] = None


class TransferResponse(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    qty: int
    from_location: TransferLocationStock
    to_location: TransferLocationStock
