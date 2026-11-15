from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.stocktake import StocktakeStatus


from app.schemas.quantity import Quantity


class StocktakeCreate(BaseModel):
    location_id: uuid.UUID
    category: Optional[str] = Field(default=None, max_length=64)


class StocktakeLineCountUpdate(BaseModel):
    counted_qty: Quantity = Field(ge=0)


class StocktakeLookupRequest(BaseModel):
    barcode: str = Field(min_length=1)


class StocktakeLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    category: Optional[str]
    expected_qty: Quantity
    counted_qty: Optional[Quantity]
    variance: Optional[Quantity]

    model_config = ConfigDict(from_attributes=True)


class StocktakeResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    location_name: str
    status: StocktakeStatus
    category: Optional[str]
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime]
    lines: list[StocktakeLineResponse]

    model_config = ConfigDict(from_attributes=True)
