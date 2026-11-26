from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PortalLoginRequest(BaseModel):
    email: str
    password: str


class PortalLoginResponse(BaseModel):
    email: str
    customer_name: str


class PortalMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    customer_id: uuid.UUID
    customer_name: str
    price_tier: str
    access_id: Optional[uuid.UUID] = None
    organisation_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class PortalUserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned:
            raise ValueError("email must contain @")
        return cleaned


class PortalInvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class PortalInvitationAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=256)


class PortalCatalogueItem(BaseModel):
    id: uuid.UUID
    our_ref: str
    name: str
    unit_ex_vat: Decimal
    unit_inc_vat: Decimal
    # The selling rule: a line's quantity is a multiple of sell_multiple, at least
    # min_sell_qty (both 1 when the SKU has none).
    sell_multiple: int
    min_sell_qty: int


class PortalOrderLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    notes: Optional[str] = None


class PortalOrderCreate(BaseModel):
    lines: list[PortalOrderLineCreate] = Field(min_length=1)
    notes: Optional[str] = None
