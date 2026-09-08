from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.pick import PickSourceType, PickStatus


class PickPreviewRequest(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)


class PickCreate(BaseModel):
    sku_id: Optional[uuid.UUID] = None
    qty: Optional[int] = Field(default=None, gt=0)
    customer_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    layby_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def validate_origin(self) -> "PickCreate":
        has_till = self.sku_id is not None
        has_invoice = self.invoice_id is not None
        has_layby = self.layby_id is not None
        if has_till + has_invoice + has_layby != 1:
            raise ValueError("Provide sku_id, invoice_id, or layby_id")
        if has_till and self.qty is None:
            raise ValueError("qty is required for a till-origin pick")
        if not has_till and self.qty is not None:
            raise ValueError("qty is only valid with sku_id")
        return self


class PickAllocationUpdate(BaseModel):
    location_id: uuid.UUID
    qty: int = Field(gt=0)


class PickLineUpdate(BaseModel):
    sku_id: uuid.UUID
    allocations: list[PickAllocationUpdate] = Field(default_factory=list)


class PickUpdate(BaseModel):
    lines: list[PickLineUpdate] = Field(min_length=1)


class PickConfirm(BaseModel):
    confirm_split: bool = False


class PickComplete(BaseModel):
    staging_location_id: Optional[uuid.UUID] = None
    collect_from_showroom: bool = False


class PickAllocationResponse(BaseModel):
    location_id: uuid.UUID
    location_name: str
    qty: int
    on_hand: int = 0

    model_config = ConfigDict(from_attributes=True)


class PickLineResponse(BaseModel):
    sku_id: uuid.UUID
    sku_our_ref: str
    sku_name: str
    qty_needed: int
    qty_allocated: int
    qty_short: int
    allocations: list[PickAllocationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PickPreviewResponse(BaseModel):
    kit_sku_id: uuid.UUID
    kit_qty: int
    needs_confirm: bool
    lines: list[PickLineResponse] = Field(default_factory=list)


class PickResponse(BaseModel):
    id: uuid.UUID
    number: str
    source_type: PickSourceType
    source_id: Optional[uuid.UUID]
    kit_sku_id: uuid.UUID
    kit_sku_our_ref: str
    kit_sku_name: str
    kit_qty: int
    status: PickStatus
    staging_location_id: Optional[uuid.UUID]
    customer_id: Optional[uuid.UUID]
    customer_name: Optional[str]
    invoice_id: Optional[uuid.UUID]
    needs_confirm: bool
    lines: list[PickLineResponse] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
