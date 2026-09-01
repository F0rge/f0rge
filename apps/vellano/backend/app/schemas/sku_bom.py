from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class SkuBomLineWrite(BaseModel):
    component_sku_id: uuid.UUID
    qty: int = Field(ge=1)


class SkuBomReplace(BaseModel):
    lines: list[SkuBomLineWrite]


class SkuBomLineResponse(BaseModel):
    id: uuid.UUID
    parent_sku_id: uuid.UUID
    component_sku_id: uuid.UUID
    qty: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
