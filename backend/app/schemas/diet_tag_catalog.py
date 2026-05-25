from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DietTagCatalogItemResponse(BaseModel):
    id: int
    key: str
    label: str
    archived: bool
    first_used_at: Optional[datetime.datetime] = None
    last_used_at: Optional[datetime.datetime] = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class DietTagCatalogItemCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)


class DietTagCatalogItemUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=128)
    archived: Optional[bool] = None
    sort_order: Optional[int] = None
