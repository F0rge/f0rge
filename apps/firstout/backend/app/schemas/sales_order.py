from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.sales_order import SalesOrderStatus


class SalesOrderLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    notes: Optional[str] = None


class SalesOrderCreate(BaseModel):
    customer_id: uuid.UUID
    lines: list[SalesOrderLineCreate] = Field(min_length=1)
    notes: Optional[str] = None


class SalesOrderPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    tender: Literal["cash", "eft"]


class SalesOrderConfirm(BaseModel):
    location_id: Optional[uuid.UUID] = None
    hold_stock: bool = False
    deposit: Optional[SalesOrderPaymentCreate] = None


class SalesOrderLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    our_ref: str
    name: str
    qty: int
    unit_ex_vat: Decimal
    description: str
    notes: Optional[str]
    held_qty: int
    hold_location_id: Optional[uuid.UUID]

    model_config = ConfigDict(from_attributes=True)


class SalesOrderPaymentResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    tender: str
    paid_on: datetime.date

    model_config = ConfigDict(from_attributes=True)


class SalesOrderListItem(BaseModel):
    id: uuid.UUID
    so_number: str
    customer_id: uuid.UUID
    customer_name: str
    quote_id: Optional[uuid.UUID]
    location_id: Optional[uuid.UUID]
    location_name: Optional[str]
    invoice_id: Optional[uuid.UUID]
    hold_stock: bool
    awaiting_stock: bool
    status: SalesOrderStatus
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    amount_paid: Decimal
    balance: Decimal
    notes: Optional[str]
    items_label: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class SalesOrderResponse(BaseModel):
    id: uuid.UUID
    so_number: str
    customer_id: uuid.UUID
    customer_name: str
    quote_id: Optional[uuid.UUID]
    location_id: Optional[uuid.UUID]
    location_name: Optional[str]
    invoice_id: Optional[uuid.UUID]
    hold_stock: bool
    awaiting_stock: bool
    status: SalesOrderStatus
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    amount_paid: Decimal
    balance: Decimal
    notes: Optional[str]
    lines: list[SalesOrderLineResponse]
    payments: list[SalesOrderPaymentResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
