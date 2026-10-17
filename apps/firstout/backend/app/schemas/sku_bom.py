from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SkuBomLineWrite(BaseModel):
    component_sku_id: uuid.UUID
    qty: Decimal = Field(gt=0, max_digits=14, decimal_places=4)


class SkuBomReplace(BaseModel):
    lines: list[SkuBomLineWrite]


class SkuBomLineResponse(BaseModel):
    id: uuid.UUID
    parent_sku_id: uuid.UUID
    component_sku_id: uuid.UUID
    qty: float
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
