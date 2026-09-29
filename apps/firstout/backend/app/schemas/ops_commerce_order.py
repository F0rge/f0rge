from __future__ import annotations

import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StorefrontAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address_1: str = Field(min_length=1, max_length=250)
    address_2: str = Field(default="", max_length=250)
    city: str = Field(min_length=1, max_length=120)
    province: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=32)
    country_code: str = Field(min_length=2, max_length=2)


class StorefrontCustomer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(min_length=1, max_length=32)
    billing_address: str = Field(default="", max_length=1000)


class StorefrontFulfillment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delivery", "collection"]
    reference: str = Field(min_length=1, max_length=255)
    recipient: str = Field(min_length=1, max_length=255)
    address: StorefrontAddress
    fee_ex_minor_zar: int = Field(ge=0)
    fee_vat_minor_zar: int = Field(ge=0)
    fee_total_minor_zar: int = Field(ge=0)

    @model_validator(mode="after")
    def fee_balances(self) -> StorefrontFulfillment:
        if self.fee_ex_minor_zar + self.fee_vat_minor_zar != self.fee_total_minor_zar:
            raise ValueError("delivery fee components do not balance")
        return self


class StorefrontOrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_line_id: str = Field(min_length=1, max_length=255)
    source_sku_id: uuid.UUID
    sku: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0, le=10000)
    unit_ex_minor_zar: int = Field(ge=0)
    ex_minor_zar: int = Field(ge=0)
    vat_minor_zar: int = Field(ge=0)
    total_minor_zar: int = Field(ge=0)

    @model_validator(mode="after")
    def line_balances(self) -> StorefrontOrderLine:
        if self.ex_minor_zar + self.vat_minor_zar != self.total_minor_zar:
            raise ValueError("order line components do not balance")
        if self.unit_ex_minor_zar * self.quantity != self.ex_minor_zar:
            raise ValueError("order line unit price does not match its subtotal")
        return self


class StorefrontOrderTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subtotal_ex_minor_zar: int = Field(ge=0)
    tax_minor_zar: int = Field(ge=0)
    delivery_ex_minor_zar: int = Field(ge=0)
    delivery_tax_minor_zar: int = Field(ge=0)
    delivery_total_minor_zar: int = Field(ge=0)
    total_minor_zar: int = Field(gt=0)


class StorefrontPayment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    reference: str = Field(min_length=1, max_length=255)
    captured_at: datetime.datetime
    amount_minor_zar: int = Field(gt=0)
    currency_code: Literal["ZAR"]


class StorefrontPaidOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: uuid.UUID
    channel: Literal["storefront"]
    external_order_id: str = Field(min_length=1, max_length=255)
    external_payment_id: str = Field(min_length=1, max_length=255)
    correlation_id: str = Field(min_length=1, max_length=255)
    currency_code: Literal["ZAR"]
    customer: StorefrontCustomer
    fulfillment: StorefrontFulfillment
    lines: list[StorefrontOrderLine] = Field(min_length=1, max_length=100)
    totals: StorefrontOrderTotals
    payment: StorefrontPayment

    @model_validator(mode="after")
    def order_balances(self) -> StorefrontPaidOrder:
        line_ex = sum(line.ex_minor_zar for line in self.lines)
        line_tax = sum(line.vat_minor_zar for line in self.lines)
        totals = self.totals
        if line_ex != totals.subtotal_ex_minor_zar:
            raise ValueError("order subtotal does not match its lines")
        if line_tax + totals.delivery_tax_minor_zar != totals.tax_minor_zar:
            raise ValueError("order tax does not match its lines and delivery")
        if (
            totals.delivery_ex_minor_zar + totals.delivery_tax_minor_zar
            != totals.delivery_total_minor_zar
        ):
            raise ValueError("delivery totals do not balance")
        expected = (
            totals.subtotal_ex_minor_zar + totals.tax_minor_zar + totals.delivery_ex_minor_zar
        )
        if expected != totals.total_minor_zar:
            raise ValueError("order total does not balance")
        if self.payment.amount_minor_zar != totals.total_minor_zar:
            raise ValueError("captured payment does not match the order total")
        if self.payment.currency_code != self.currency_code:
            raise ValueError("payment currency does not match the order currency")
        if len({line.external_line_id for line in self.lines}) != len(self.lines):
            raise ValueError("external order line identities must be unique")
        return self


class StorefrontHandoffResponse(BaseModel):
    id: uuid.UUID
    external_order_id: str
    correlation_id: str
    status: Literal["pending", "processing", "stock_conflict", "imported", "failed"]
    failure_code: Optional[str]
    attempt_count: int
    last_attempt_at: Optional[datetime.datetime]
    imported_at: Optional[datetime.datetime]
    sales_order_id: uuid.UUID
    payment_journal_id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


class StorefrontHandoffListResponse(BaseModel):
    items: list[StorefrontHandoffResponse]
