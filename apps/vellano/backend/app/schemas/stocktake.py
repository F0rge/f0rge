from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.stocktake import StocktakeStatus


class StocktakeCreate(BaseModel):
    location_id: uuid.UUID


class StocktakeLineCountUpdate(BaseModel):
    counted_qty: int = Field(ge=0)


class StocktakeLookupRequest(BaseModel):
    barcode: str = Field(min_length=1)


class StocktakeLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    expected_qty: int
    counted_qty: Optional[int]
    variance: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class StocktakeResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    location_name: str
    status: StocktakeStatus
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime]
    lines: list[StocktakeLineResponse]

    model_config = ConfigDict(from_attributes=True)
