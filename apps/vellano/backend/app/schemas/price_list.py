from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class PriceListItemResponse(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    unit_ex_vat: Decimal


class PriceListResponse(BaseModel):
    id: uuid.UUID
    name: str
    items: list[PriceListItemResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PriceListCreate(BaseModel):
    name: str = Field(min_length=1)


class PriceListUpdate(BaseModel):
    name: str = Field(min_length=1)


class PriceListItemUpsert(BaseModel):
    sku_id: uuid.UUID
    unit_ex_vat: Decimal = Field(gt=0)
