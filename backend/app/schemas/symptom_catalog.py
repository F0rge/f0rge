from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SymptomCatalogItemResponse(BaseModel):
    id: int
    key: str
    label: str
    archived: bool
    first_used_at: Optional[datetime.datetime] = None
    last_used_at: Optional[datetime.datetime] = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class SymptomCatalogItemCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)


class SymptomCatalogItemUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=128)
    archived: Optional[bool] = None
    sort_order: Optional[int] = None


class SymptomOrderRequest(BaseModel):
    order: list[str]

    @field_validator("order")
    @classmethod
    def no_duplicates(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("order must not contain duplicate keys")
        return v
