"""Review and confirm payloads for supplier document reading."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.proforma import ProformaResponse
from app.schemas.purchase_order import PurchaseOrderResponse
from app.schemas.sku import SkuResponse


class ModelUsage(BaseModel):
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ReviewFlag(BaseModel):
    code: str
    message: str


class ExtractedParty(BaseModel):
    name: str = ""
    vat_number: Optional[str] = None
    address: Optional[str] = None


class ExtractedLine(BaseModel):
    supplier_code: Optional[str] = None
    description: str = ""
    qty: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    discount_percent: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    line_total: Optional[Decimal] = None


class ExtractedCharge(BaseModel):
    description: str = ""
    amount: Decimal = Decimal("0")


class ExtractedDocument(BaseModel):
    document_kind: str = "proforma"
    supplier: ExtractedParty = Field(default_factory=ExtractedParty)
    document_number: str = ""
    document_date: Optional[datetime.date] = None
    currency: str = "ZAR"
    po_reference: Optional[str] = None
    proforma_number: Optional[str] = None
    lines: list[ExtractedLine] = Field(default_factory=list)
    charges: list[ExtractedCharge] = Field(default_factory=list)
    subtotal: Optional[Decimal] = None
    vat_total: Optional[Decimal] = None
    total: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    deposit: Optional[str] = None


class SupplierMatchOut(BaseModel):
    supplier_id: Optional[uuid.UUID] = None
    name: str
    vat_number: Optional[str] = None
    address: Optional[str] = None
    confidence: float
    reason: str


class SkuMatchOut(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    confidence: float
    reason: str


class ChargeOut(BaseModel):
    description: str
    amount: str


class ReviewedLine(BaseModel):
    supplier_code: Optional[str] = None
    description: str
    qty: str
    qty_whole: Optional[int] = None
    unit_price: str
    discount_percent: Optional[str] = None
    discount_amount: Optional[str] = None
    net_unit_price: str
    vat_rate: Optional[str] = None
    vat_amount: Optional[str] = None
    line_total: Optional[str] = None
    match: Optional[SkuMatchOut] = None
    alternatives: list[SkuMatchOut] = Field(default_factory=list)
    flags: list[ReviewFlag] = Field(default_factory=list)


class ProformaReview(BaseModel):
    supplier: SupplierMatchOut
    supplier_candidates: list[SupplierMatchOut] = Field(default_factory=list)
    document_number: str
    document_date: Optional[datetime.date] = None
    currency: str
    payment_terms: Optional[str] = None
    deposit: Optional[str] = None
    lines: list[ReviewedLine]
    charges: list[ChargeOut]
    subtotal: Optional[str] = None
    vat_total: Optional[str] = None
    total: Optional[str] = None
    computed_total: str
    flags: list[ReviewFlag]
    usage: ModelUsage


class NewSupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    vat_number: Optional[str] = Field(default=None, max_length=64)
    address: Optional[str] = None
    default_currency: Optional[str] = Field(default=None, max_length=3)


class ChargeIn(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(ge=0)


class ConfirmLineIn(BaseModel):
    supplier_code: Optional[str] = Field(default=None, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    qty: int = Field(ge=1)
    unit_price: Decimal = Field(gt=0)
    discount_percent: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    sku_id: Optional[uuid.UUID] = None
    skip: bool = False


class ProformaConfirmIn(BaseModel):
    supplier_id: Optional[uuid.UUID] = None
    create_supplier: Optional[NewSupplierIn] = None
    document_number: str = Field(min_length=1, max_length=64)
    document_date: datetime.date
    currency: str = Field(min_length=3, max_length=3)
    payment_terms: Optional[str] = None
    deposit: Optional[str] = None
    vat_total: Optional[Decimal] = None
    total: Optional[Decimal] = None
    charges: list[ChargeIn] = Field(default_factory=list)
    lines: list[ConfirmLineIn] = Field(min_length=1)


class ProformaConfirmResponse(BaseModel):
    proforma: ProformaResponse
    purchase_order: PurchaseOrderResponse


class PurchaseOrderMatchOut(BaseModel):
    purchase_order_id: uuid.UUID
    po_number: str
    status: str
    supplier_id: uuid.UUID
    supplier_name: str


class ProcessedBillOut(BaseModel):
    bill_id: uuid.UUID
    bill_number: str
    auto: bool
    purchase_order_id: uuid.UUID
    po_number: str


class InvoiceReview(ProformaReview):
    po_reference: Optional[str] = None
    proforma_number: Optional[str] = None
    purchase_order: Optional[PurchaseOrderMatchOut] = None
    purchase_order_candidates: list[PurchaseOrderMatchOut] = Field(default_factory=list)
    exact: bool = False
    differences: list[str] = Field(default_factory=list)
    auto_process_enabled: bool = False
    needs_fx: bool = False
    processed: Optional[ProcessedBillOut] = None


class InvoiceProcessIn(BaseModel):
    supplier_id: Optional[uuid.UUID] = None
    create_supplier: Optional[NewSupplierIn] = None
    purchase_order_id: uuid.UUID
    document_number: str = Field(min_length=1, max_length=64)
    document_date: datetime.date
    currency: str = Field(min_length=3, max_length=3)
    fx_to_zar: Optional[Decimal] = None
    accept_differences: bool = False
    vat_total: Optional[Decimal] = None
    total: Optional[Decimal] = None
    charges: list[ChargeIn] = Field(default_factory=list)
    lines: list[ConfirmLineIn] = Field(min_length=1)


class SkuSuggestIn(BaseModel):
    description: str = Field(min_length=1)
    supplier_code: Optional[str] = None
    unit_price: Optional[Decimal] = None
    currency: Optional[str] = None
    vat_rate: Optional[Decimal] = None
    hint: Optional[str] = None
    supplier_id: Optional[uuid.UUID] = None


class SkuSuggestion(BaseModel):
    our_ref: str
    our_barcode: str
    name: str
    design: str
    fabric: str
    supplier_ref: Optional[str] = None
    category: Optional[str] = None
    cost_price: Optional[str] = None
    vat_rate: Optional[str] = None
    source: str


class IntakeSkuCreate(BaseModel):
    our_ref: str = Field(min_length=1, max_length=64)
    our_barcode: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    design: str = Field(min_length=1)
    fabric: str = Field(min_length=1)
    supplier_ref: Optional[str] = Field(default=None, max_length=64)
    category: Optional[str] = Field(default=None, max_length=64)
    carton_count: int = Field(default=1, ge=1)
    supplier_id: uuid.UUID
    supplier_sku: Optional[str] = Field(default=None, max_length=128)
    latest_price: Optional[Decimal] = Field(default=None, gt=0)


class IntakeSkuResponse(BaseModel):
    sku: SkuResponse
    supplier_price_id: uuid.UUID
