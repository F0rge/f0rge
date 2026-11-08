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
    max_till_discount_percent: Optional[Decimal] = None
    po_approval_threshold_zar: Optional[Decimal] = None
    auto_process_exact_supplier_invoices: bool = False
    session_ttl_hours: int
    label_width_mm: int = 100
    label_height_mm: int = 60
    label_show_name: bool = True
    label_show_reference: bool = True
    label_show_barcode: bool = True
    label_show_logo: bool = False
    has_logo: bool = False
    document_sequences: list[DocumentSequenceResponse]


class SettingsUpdate(BaseModel):
    label_width_mm: Optional[int] = Field(default=None, ge=20, le=300)
    label_height_mm: Optional[int] = Field(default=None, ge=10, le=300)
    label_show_name: Optional[bool] = None
    label_show_reference: Optional[bool] = None
    label_show_barcode: Optional[bool] = None
    label_show_logo: Optional[bool] = None
    vat_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    home_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    always_prefer_warehouse: Optional[bool] = None
    pick_priority: Optional[list[uuid.UUID]] = None
    legal_name: Optional[str] = Field(default=None, min_length=1)
    trading_name: Optional[str] = None
    address: Optional[str] = None
    vat_number: Optional[str] = None
    cipc_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_branch_code: Optional[str] = None
    payment_terms_days: Optional[int] = Field(default=None, ge=0, le=365)
    default_receive_location_id: Optional[uuid.UUID] = None
    default_till_location_id: Optional[uuid.UUID] = None
    max_till_discount_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    po_approval_threshold_zar: Optional[Decimal] = Field(default=None, ge=0)
    auto_process_exact_supplier_invoices: Optional[bool] = None
    session_ttl_hours: Optional[int] = Field(default=None, ge=1, le=720)
    document_sequences: Optional[list[DocumentSequenceUpdateItem]] = None
