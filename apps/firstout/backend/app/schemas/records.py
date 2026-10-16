from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class AddressResponse(BaseModel):
    id: uuid.UUID
    address_type: Optional[str]
    is_default: bool
    line1: Optional[str]
    line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postcode: Optional[str]
    country: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ContactResponse(BaseModel):
    id: uuid.UUID
    name: Optional[str]
    job_title: Optional[str]
    phone: Optional[str]
    mobile: Optional[str]
    fax: Optional[str]
    email: Optional[str]
    website: Optional[str]
    comment: Optional[str]
    is_default: bool
    include_in_emails: bool

    model_config = ConfigDict(from_attributes=True)


class SupplierPriceRow(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    sku_id: uuid.UUID
    our_ref: str
    sku_name: str
    supplier_sku: Optional[str]
    currency: str
    # Null without ``stock.cost.view``.
    latest_price: Optional[Decimal]
    fixed_price: Optional[Decimal]


class SalesHistoryRow(BaseModel):
    kind: Literal["invoice", "credit_note"]
    document_id: uuid.UUID
    document_number: str
    issue_date: datetime.date
    customer_id: Optional[uuid.UUID]
    customer_name: Optional[str]
    sku_id: Optional[uuid.UUID]
    our_ref: Optional[str]
    description: str
    qty: Decimal
    ex_vat: Decimal
    vat_amount: Decimal
    inc_vat: Decimal


class PurchaseHistoryRow(BaseModel):
    bill_id: uuid.UUID
    bill_number: str
    issue_date: datetime.date
    supplier_id: uuid.UUID
    supplier_name: str
    description: str
    qty: int
    currency: str
    # Amounts are null without ``stock.cost.view``. ``amount_zar`` is also null when the
    # bill is foreign-currency history with no known ZAR rate.
    unit_amount: Optional[Decimal]
    amount_foreign: Optional[Decimal]
    fx_rate_known: bool
    bill_amount_zar: Optional[Decimal]


class StockByBinRow(BaseModel):
    location_id: uuid.UUID
    location_name: str
    bin_id: uuid.UUID
    bin_code: str
    sku_id: uuid.UUID
    our_ref: str
    sku_name: str
    on_hand: int
