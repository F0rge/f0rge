from __future__ import annotations

import datetime
import uuid

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SkuCreate(BaseModel):
    our_ref: str = Field(min_length=1, max_length=64)
    our_barcode: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    design: str = Field(min_length=1)
    fabric: str = Field(min_length=1)
    supplier_ref: Optional[str] = Field(default=None, max_length=64)


class SkuResponse(BaseModel):
    id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    design: str
    fabric: str
    supplier_ref: Optional[str]
    photo_storage_key: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
