from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SkuCreate(BaseModel):
    our_ref: str = Field(min_length=1, max_length=64)
    our_barcode: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    design: str = Field(min_length=1)
    fabric: str = Field(min_length=1)
    supplier_ref: Optional[str] = Field(default=None, max_length=64)
    category: Optional[str] = Field(default=None, max_length=64)
    opening_location_id: Optional[uuid.UUID] = None
    opening_qty: Optional[int] = Field(default=None, ge=1)
    opening_unit_cost_zar: Optional[Decimal] = Field(default=None, gt=0)
    opening_date: Optional[datetime.date] = None
    carton_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def opening_fields_together(self) -> SkuCreate:
        any_opening = any(
            [
                self.opening_location_id is not None,
                self.opening_qty is not None,
                self.opening_unit_cost_zar is not None,
                self.opening_date is not None,
            ]
        )
        if not any_opening:
            return self
        if (
            self.opening_location_id is None
            or self.opening_qty is None
            or self.opening_unit_cost_zar is None
        ):
            raise ValueError(
                "opening_location_id, opening_qty, and opening_unit_cost_zar "
                "are required when any opening field is set"
            )
        return self


class SkuUpdate(BaseModel):
    our_ref: Optional[str] = Field(default=None, min_length=1, max_length=64)
    our_barcode: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1)
    design: Optional[str] = Field(default=None, min_length=1)
    fabric: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, max_length=64)
    preferred_supplier_id: Optional[uuid.UUID] = None
    lead_time_days: Optional[int] = Field(default=None, ge=0)
    reorder_min: Optional[int] = Field(default=None, ge=1)
    supplier_ref: Optional[str] = Field(default=None, max_length=64)
    wholesale_ex_vat: Optional[Decimal] = None
    wholesale_inc_vat: Optional[Decimal] = None
    retail_ex_vat: Optional[Decimal] = None
    retail_inc_vat: Optional[Decimal] = None
    carton_count: Optional[int] = Field(default=None, ge=1)


class SkuResponse(BaseModel):
    id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    design: str
    fabric: str
    supplier_ref: Optional[str]
    preferred_supplier_id: Optional[uuid.UUID] = None
    preferred_supplier_name: Optional[str] = None
    lead_time_days: Optional[int] = None
    reorder_min: Optional[int] = None
    last_landed_cost_zar: Optional[Decimal] = None
    category: Optional[str] = None
    photo_storage_key: Optional[str]
    wholesale_ex_vat: Optional[Decimal] = None
    wholesale_inc_vat: Optional[Decimal] = None
    retail_ex_vat: Optional[Decimal] = None
    retail_inc_vat: Optional[Decimal] = None
    carton_count: int
    is_kit: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
