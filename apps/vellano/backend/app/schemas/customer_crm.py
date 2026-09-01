from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

CustomerType = Literal["retail", "trade"]


class CustomerCrmCreate(BaseModel):
    name: str = Field(min_length=1)
    email: Optional[str] = None
    phone: Optional[str] = None
    vat_number: Optional[str] = None
    billing_address: Optional[str] = None
    customer_type: CustomerType = "retail"
    price_tier: str = "standard"


class CustomerCrmUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[str] = None
    phone: Optional[str] = None
    vat_number: Optional[str] = None
    billing_address: Optional[str] = None
    customer_type: Optional[CustomerType] = None
    price_tier: Optional[str] = None


class CustomerCrmResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    vat_number: Optional[str] = None
    billing_address: Optional[str] = None
    customer_type: CustomerType
    price_tier: str
    open_invoices_count: int
    open_invoices_zar: Decimal
    overdue_invoices_count: int
    active_laybys_count: int
    active_laybys_zar: Decimal
    created_at: datetime.datetime
    updated_at: datetime.datetime
