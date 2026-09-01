from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.transfer import TransferStatus


class TransferLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    from_bin_id: Optional[uuid.UUID] = None
    to_bin_id: Optional[uuid.UUID] = None


class TransferCreate(BaseModel):
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    notes: Optional[str] = None
    lines: list[TransferLineCreate] = Field(min_length=1)


class TransferReceiveLine(BaseModel):
    line_id: uuid.UUID
    qty_received: int = Field(ge=0)


class TransferReceive(BaseModel):
    lines: list[TransferReceiveLine] = Field(min_length=1)


class TransferLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    sku_our_ref: str
    sku_name: str
    qty_dispatched: int
    qty_received: Optional[int]
    from_bin_id: Optional[uuid.UUID]
    to_bin_id: Optional[uuid.UUID]
    unit_cost_zar: Optional[Decimal]

    model_config = ConfigDict(from_attributes=True)


class TransferResponse(BaseModel):
    id: uuid.UUID
    transfer_number: str
    status: TransferStatus
    from_location_id: uuid.UUID
    from_location_name: str
    to_location_id: uuid.UUID
    to_location_name: str
    notes: Optional[str]
    created_by_user_id: uuid.UUID
    dispatched_at: Optional[datetime.datetime]
    dispatched_by_user_id: Optional[uuid.UUID]
    received_at: Optional[datetime.datetime]
    received_by_user_id: Optional[uuid.UUID]
    received_display_name: Optional[str]
    lines: list[TransferLineResponse] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
