from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.lookbook import LookbookPriceMode


class LookbookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    customer_id: Optional[uuid.UUID] = None
    price_mode: LookbookPriceMode
    price_list_id: Optional[uuid.UUID] = None
    sku_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    expires_in_days: int = Field(default=14, ge=1, le=90)


class LookbookItemStaff(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    position: int
    name: str
    our_ref: str
    unit_inc_vat: Optional[Decimal]

    model_config = ConfigDict(from_attributes=True)


class LookbookListItem(BaseModel):
    id: uuid.UUID
    name: str
    customer_id: Optional[uuid.UUID]
    customer_name: Optional[str]
    price_mode: LookbookPriceMode
    sku_count: int
    token: str
    expires_at: datetime.datetime
    revoked_at: Optional[datetime.datetime]
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class LookbookResponse(LookbookListItem):
    price_list_id: Optional[uuid.UUID]
    items: list[LookbookItemStaff]


class PublicLookbookItem(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    position: int
    name: str
    our_ref: str
    unit_inc_vat: Optional[Decimal]
    photo_path: Optional[str]


class PublicLookbookResponse(BaseModel):
    company_name: str
    name: str
    price_mode: LookbookPriceMode
    expires_at: datetime.datetime
    items: list[PublicLookbookItem]
