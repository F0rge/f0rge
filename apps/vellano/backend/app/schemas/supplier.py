from __future__ import annotations

import datetime
import uuid

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1)
    default_currency: Optional[str] = Field(default=None, max_length=3)


class SupplierResponse(BaseModel):
    id: uuid.UUID
    name: str
    default_currency: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
