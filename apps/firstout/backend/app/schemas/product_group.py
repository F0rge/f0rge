from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class ProductGroupVariantInput(BaseModel):
    source_sku_id: uuid.UUID
    options: dict[str, str]


class ProductGroupCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    options: dict[str, list[str]]
    variants: list[ProductGroupVariantInput] = Field(default_factory=list)


class ProductGroupUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    options: Optional[dict[str, list[str]]] = None
    storefront_published: Optional[bool] = None


class ProductGroupVariantsReplace(BaseModel):
    variants: list[ProductGroupVariantInput]


class ProductGroupVariantResponse(BaseModel):
    source_sku_id: uuid.UUID
    sku: str
    name: str
    options: dict[str, str]


class ProductGroupResponse(BaseModel):
    id: uuid.UUID
    title: str
    options: dict[str, list[str]]
    storefront_published: bool
    variants: list[ProductGroupVariantResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime
