from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class DocumentSequenceResponse(BaseModel):
    doc_type: str
    prefix: str
    padding: int
    next_value: int


class DocumentSequenceUpdateItem(BaseModel):
    doc_type: str
    prefix: Optional[str] = None
    padding: Optional[int] = Field(default=None, ge=1, le=12)


class SettingsResponse(BaseModel):
    vat_rate: Decimal
    vat_percent: Decimal
    home_currency: str
    defaults_locked: bool
    warning: Optional[str] = None
    always_prefer_warehouse: bool
    pick_priority: list[uuid.UUID]
    nia_monthly_token_cap: int
    legal_name: str
    trading_name: Optional[str] = None
    address: str
    vat_number: str
    cipc_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_branch_code: Optional[str] = None
    payment_terms_days: int
    default_receive_location_id: Optional[uuid.UUID] = None
    default_till_location_id: Optional[uuid.UUID] = None
    document_sequences: list[DocumentSequenceResponse]


class SettingsUpdate(BaseModel):
    vat_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    home_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    always_prefer_warehouse: Optional[bool] = None
    pick_priority: Optional[list[uuid.UUID]] = None
    nia_monthly_token_cap: Optional[int] = Field(default=None, ge=0)
    legal_name: Optional[str] = Field(default=None, min_length=1)
    trading_name: Optional[str] = None
    address: Optional[str] = Field(default=None, min_length=1)
    vat_number: Optional[str] = Field(default=None, min_length=1)
    cipc_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_branch_code: Optional[str] = None
    payment_terms_days: Optional[int] = Field(default=None, ge=0, le=365)
    default_receive_location_id: Optional[uuid.UUID] = None
    default_till_location_id: Optional[uuid.UUID] = None
    document_sequences: Optional[list[DocumentSequenceUpdateItem]] = None
