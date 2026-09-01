from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.delivery import DeliverySourceType, DeliveryStatus


class DeliveryCreate(BaseModel):
    source_type: DeliverySourceType
    invoice_id: Optional[uuid.UUID] = None
    layby_id: Optional[uuid.UUID] = None
    location_id: uuid.UUID
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_source_ids(self) -> "DeliveryCreate":
        if self.source_type == DeliverySourceType.INVOICE:
            if self.invoice_id is None or self.layby_id is not None:
                raise ValueError("invoice source requires invoice_id and no layby_id")
        elif self.source_type == DeliverySourceType.LAYBY:
            if self.layby_id is None or self.invoice_id is not None:
                raise ValueError("layby source requires layby_id and no invoice_id")
        return self


class DeliveryComplete(BaseModel):
    delivery_date: Optional[datetime.date] = None


class DeliveryLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: Optional[uuid.UUID]
    description: str
    qty: int

    model_config = ConfigDict(from_attributes=True)


class DeliveryResponse(BaseModel):
    id: uuid.UUID
    delivery_number: str
    source_type: DeliverySourceType
    invoice_id: Optional[uuid.UUID]
    invoice_number: Optional[str]
    layby_id: Optional[uuid.UUID]
    layby_number: Optional[str]
    customer_name: str
    location_id: uuid.UUID
    location_name: str
    status: DeliveryStatus
    delivery_date: Optional[datetime.date]
    notes: Optional[str]
    lines: list[DeliveryLineResponse] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
