from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.quantity import QuantityTotal


class SkuSearchHit(BaseModel):
    id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    category: Optional[str] = None
    has_photo: bool = False
    retail_inc_vat: Optional[Decimal] = None
    # Company availability (StockAvailability), never below zero.
    available: QuantityTotal = Decimal(0)
    is_kit: bool = False
    sell_multiple: int = 1
    min_sell_qty: int = 1


class PurchaseOrderSearchHit(BaseModel):
    id: uuid.UUID
    po_number: str
    status: str
    supplier_name: str


class InvoiceSearchHit(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_name: str


class SearchResponse(BaseModel):
    q: str
    skus: list[SkuSearchHit] = Field(default_factory=list)
    purchase_orders: list[PurchaseOrderSearchHit] = Field(default_factory=list)
    invoices: list[InvoiceSearchHit] = Field(default_factory=list)
