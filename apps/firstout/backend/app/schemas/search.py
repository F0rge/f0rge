from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SkuSearchHit(BaseModel):
    id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str


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
