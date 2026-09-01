from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PoLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(ge=1)
    factory_unit_amount: Decimal = Field(gt=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    proforma_id: Optional[uuid.UUID] = None
    lines: list[PoLineCreate] = Field(min_length=1)


class PoLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    fabric: str
    qty: int
    factory_unit_amount: Decimal
    unit_cost_zar: Optional[Decimal] = None


class LandingBillResponse(BaseModel):
    kind: str
    invoice_number: str
    amount: Decimal
    currency: str


class PurchaseOrderResponse(BaseModel):
    id: uuid.UUID
    po_number: str
    status: str
    supplier_id: uuid.UUID
    supplier_name: str
    proforma_id: Optional[uuid.UUID] = None
    fx_to_zar: Optional[Decimal] = None
    lines: list[PoLineResponse]
    bills: list[LandingBillResponse]
    received_location_id: Optional[uuid.UUID] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ReceiveRequest(BaseModel):
    purchase_order_id: uuid.UUID
    location_id: uuid.UUID
