"""SKU overview (side panel and full view) and the SKU's supplier price rows."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.inventory import LocationStockResponse
from app.schemas.quantity import Quantity, QuantityTotal
from app.schemas.sku import SkuResponse

SupplierPrice = Annotated[
    Decimal, Field(ge=0, max_digits=18, decimal_places=4, allow_inf_nan=False)
]
SupplierQuantity = Annotated[int, Field(ge=1, le=1_000_000, strict=True)]


class SkuSupplierPriceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID
    supplier_sku: Optional[str] = Field(default=None, max_length=128)
    # Ignored (kept as stored) when null and the caller cannot see costs.
    latest_price: Optional[SupplierPrice] = None
    fixed_price: Optional[SupplierPrice] = None
    min_order_qty: Optional[SupplierQuantity] = None
    pack_multiple: Optional[SupplierQuantity] = None


class SkuSupplierPricesReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[SkuSupplierPriceWrite] = Field(max_length=50)


class SkuSupplierPriceResponse(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_is_archived: bool
    # The preferred supplier's row is the one reorder reads.
    is_preferred: bool
    supplier_sku: Optional[str] = None
    latest_price: Optional[Decimal] = None
    fixed_price: Optional[Decimal] = None
    min_order_qty: Optional[int] = None
    pack_multiple: Optional[int] = None
    updated_at: datetime.datetime


class SkuHeldDocument(BaseModel):
    kind: Literal["sales_order", "layby"]
    id: uuid.UUID
    number: str
    qty: QuantityTotal


class SkuNextArrival(BaseModel):
    purchase_order_id: uuid.UUID
    po_number: str
    status: Literal["open", "on_water", "landed"]
    qty: QuantityTotal
    # Only when it can be derived honestly: ordered date plus the SKU's planned lead time.
    expected_on: Optional[datetime.date] = None
    expected_on_basis: Optional[Literal["planned_lead_time"]] = None


class SkuOverviewStock(BaseModel):
    on_hand: QuantityTotal
    held: QuantityTotal
    held_documents: list[SkuHeldDocument]
    available: QuantityTotal
    on_order: QuantityTotal
    next_arrival: Optional[SkuNextArrival] = None
    # Weighted average over locations; null without stock.cost.view.
    unit_cost_zar: Optional[Decimal] = None
    locations: list[LocationStockResponse]


class SkuKitUse(BaseModel):
    parent_sku_id: uuid.UUID
    our_ref: str
    name: str
    qty: Quantity
    parent_is_archived: bool


class SkuActivityEntry(BaseModel):
    id: uuid.UUID
    source: str
    source_label: str
    location_id: Optional[uuid.UUID] = None
    location_name: Optional[str] = None
    created_at: datetime.datetime
    note: Optional[str] = None
    # Null without stock.cost.view.
    old_cost_zar: Optional[Decimal] = None
    new_cost_zar: Optional[Decimal] = None


class SkuOverviewResponse(BaseModel):
    sku: SkuResponse
    stock: SkuOverviewStock
    supplier_prices: list[SkuSupplierPriceResponse]
    is_kit: bool
    used_in_kits: list[SkuKitUse]
    activity: list[SkuActivityEntry]
