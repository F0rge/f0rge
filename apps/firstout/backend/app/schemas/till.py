from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.invoice import InvoiceLineResponse


from app.schemas.quantity import Quantity


class TillSaleLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)


class TillPriceRequest(BaseModel):
    lines: list[TillSaleLineCreate] = Field(min_length=1)
    customer_id: Optional[uuid.UUID] = None


class TillPriceLine(BaseModel):
    sku_id: uuid.UUID
    qty: int
    discount_percent: Decimal
    unit_ex_vat: Decimal
    before_discount_ex_vat: Decimal
    ex_vat: Decimal
    vat_amount: Decimal
    inc_vat: Decimal
    source: str
    price_warning: Optional[str] = None


class TillPricePreview(BaseModel):
    classification: str
    price_list_name: Optional[str]
    prices_include_vat: bool
    before_discount_ex_vat: Decimal
    before_discount_inc_vat: Decimal
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    lines: list[TillPriceLine]
    price_revision: str


class TillSaleCreate(TillPriceRequest):
    location_id: uuid.UUID
    tender: Literal["cash", "card", "deposit", "eft"]
    price_revision: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    pick_id: Optional[uuid.UUID] = None
    pick_ids: list[uuid.UUID] = Field(default_factory=list)
    credit_override: bool = False
    credit_override_reason: Optional[str] = None
    # Complete from the caller's server basket; it is emptied with the sale.
    basket_id: Optional[uuid.UUID] = None
    basket_version: Optional[int] = Field(default=None, ge=1)


class TillSaleLocationStock(BaseModel):
    location_id: uuid.UUID
    location_name: str
    on_hand: Quantity


class TillSaleResponse(BaseModel):
    invoice_id: uuid.UUID
    # The draft pick for units reserved against the invoice, when stock was sold from elsewhere.
    pick_id: Optional[uuid.UUID] = None
    invoice_number: str
    payment_id: uuid.UUID
    payment_number: str
    tender: Literal["cash", "card", "deposit", "eft"]
    issue_date: datetime.date
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    prices_include_vat: bool
    lines: list[InvoiceLineResponse]
    location: TillSaleLocationStock

    model_config = ConfigDict(from_attributes=True)
