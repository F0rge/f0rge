from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


from app.schemas.quantity import Quantity
from app.schemas.sku import SkuColourName, SkuOtherMaterialIds


class PoLineCreate(BaseModel):
    sku_id: Optional[uuid.UUID] = None
    supplier_code: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    notes: Optional[str] = None
    qty: int = Field(ge=1)
    factory_unit_amount: Decimal = Field(gt=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    proforma_id: Optional[uuid.UUID] = None
    supplier_ref: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = None
    submit_for_approval: bool = False
    lines: list[PoLineCreate] = Field(min_length=1)


class PoLineWrite(BaseModel):
    id: Optional[uuid.UUID] = None
    sku_id: Optional[uuid.UUID] = None
    supplier_code: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    notes: Optional[str] = None
    qty: int = Field(ge=1)
    factory_unit_amount: Decimal = Field(gt=0)


class PurchaseOrderLinesUpdate(BaseModel):
    supplier_ref: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = None
    lines: list[PoLineWrite] = Field(min_length=1)


class PoLineSkuCreate(BaseModel):
    our_ref: str = Field(min_length=1, max_length=64)
    our_barcode: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    design: str = Field(min_length=1)
    # Deprecated: see SkuCreate.fabric and SkuCreate.category.
    fabric: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, max_length=64)
    category_id: Optional[uuid.UUID] = None
    subcategory_id: Optional[uuid.UUID] = None
    colour_name: SkuColourName = None
    main_material_id: Optional[uuid.UUID] = None
    other_material_ids: SkuOtherMaterialIds = Field(default_factory=list)


class PoLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: Optional[uuid.UUID] = None
    our_ref: Optional[str] = None
    our_barcode: Optional[str] = None
    name: str
    fabric: Optional[str] = None
    supplier_code: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    needs_sku: bool = False
    qty: Quantity
    factory_unit_amount: Optional[Decimal]
    unit_cost_zar: Optional[Decimal] = None
    source_cost: Optional[str] = None
    source_total: Optional[str] = None


class LandingBillResponse(BaseModel):
    kind: str
    invoice_number: str
    amount: Decimal
    currency: str


class PurchaseOrderListItem(BaseModel):
    is_archive: bool = False
    source_amounts_known: bool = True
    source_currency_known: bool = True
    id: uuid.UUID
    po_number: str
    status: str
    supplier_id: uuid.UUID
    supplier_name: str
    proforma_id: Optional[uuid.UUID] = None
    supplier_ref: Optional[str] = None
    notes: Optional[str] = None
    fx_to_zar: Optional[Decimal] = None
    line_count: int
    needs_sku_count: int = 0
    received_location_id: Optional[uuid.UUID] = None
    ordered_at: Optional[datetime.datetime] = None
    on_water_at: Optional[datetime.datetime] = None
    landed_at: Optional[datetime.datetime] = None
    received_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PurchaseOrderResponse(BaseModel):
    is_archive: bool = False
    source_amounts_known: bool = True
    source_currency_known: bool = True
    id: uuid.UUID
    po_number: str
    status: str
    supplier_id: uuid.UUID
    supplier_name: str
    proforma_id: Optional[uuid.UUID] = None
    supplier_ref: Optional[str] = None
    notes: Optional[str] = None
    fx_to_zar: Optional[Decimal] = None
    needs_sku_count: int = 0
    lines: list[PoLineResponse]
    bills: list[LandingBillResponse]
    received_location_id: Optional[uuid.UUID] = None
    ordered_at: Optional[datetime.datetime] = None
    on_water_at: Optional[datetime.datetime] = None
    landed_at: Optional[datetime.datetime] = None
    received_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ReceiveRequest(BaseModel):
    purchase_order_id: uuid.UUID
    location_id: uuid.UUID
    bin_id: Optional[uuid.UUID] = None
