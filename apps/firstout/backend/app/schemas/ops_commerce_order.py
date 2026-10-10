from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)


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


class StorefrontLinePromise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stocked", "made_to_order"]
    offer_id: Optional[uuid.UUID] = None
    min_lead_time_days: Optional[int] = Field(default=None, ge=0)
    max_lead_time_days: Optional[int] = Field(default=None, ge=0)
    estimated_from: datetime.date
    estimated_by: datetime.date
    expires_at: Optional[datetime.datetime] = None

    @model_validator(mode="after")
    def validate_promise(self) -> StorefrontLinePromise:
        if self.estimated_by < self.estimated_from:
            raise ValueError("promise end date precedes its start date")
        if self.kind == "made_to_order":
            if (
                self.offer_id is None
                or self.min_lead_time_days is None
                or self.max_lead_time_days is None
            ):
                raise ValueError("made-to-order promise requires its offer and lead-time range")
            if self.max_lead_time_days < self.min_lead_time_days:
                raise ValueError("maximum lead time precedes minimum lead time")
            if self.expires_at is None:
                raise ValueError("made-to-order promise requires its offer expiry")
        return self


class StorefrontOrderPromise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    kind: Literal["stocked", "made_to_order", "mixed"]
    accepted_at: datetime.datetime
    estimated_from: datetime.date
    estimated_by: datetime.date

    @model_validator(mode="after")
    def validate_window(self) -> StorefrontOrderPromise:
        if self.estimated_by < self.estimated_from:
            raise ValueError("promise end date precedes its start date")
        return self


class StorefrontOrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_line_id: str = Field(min_length=1, max_length=255)
    source_sku_id: uuid.UUID
    sku: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0, le=10000)
    unit_ex_minor_zar: int = Field(ge=0)
    unit_ex_remainder_minor_zar: int = Field(default=0, ge=0)
    ex_minor_zar: int = Field(ge=0)
    vat_minor_zar: int = Field(ge=0)
    total_minor_zar: int = Field(ge=0)
    fulfillment_promise: Optional[StorefrontLinePromise] = None

    @model_validator(mode="after")
    def line_balances(self) -> StorefrontOrderLine:
        if self.ex_minor_zar + self.vat_minor_zar != self.total_minor_zar:
            raise ValueError("order line components do not balance")
        if self.unit_ex_remainder_minor_zar >= self.quantity:
            raise ValueError("order line unit rounding remainder exceeds its quantity")
        if (
            self.unit_ex_minor_zar * self.quantity + self.unit_ex_remainder_minor_zar
            != self.ex_minor_zar
        ):
            raise ValueError("order line unit price does not match its subtotal")
        return self

    @model_serializer(mode="wrap")
    def serialize_allocation(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload = handler(self)
        # Keep existing canonical hashes unchanged when no unit cent allocation is needed.
        if self.unit_ex_remainder_minor_zar == 0:
            payload.pop("unit_ex_remainder_minor_zar", None)
        return payload


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
    fulfillment_promise: Optional[StorefrontOrderPromise] = None

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
        line_promises = [line.fulfillment_promise for line in self.lines]
        if self.fulfillment_promise is None and any(
            promise is not None and promise.kind == "made_to_order" for promise in line_promises
        ):
            raise ValueError("made-to-order lines require an order fulfillment promise")
        if self.fulfillment_promise is not None:
            if any(promise is None for promise in line_promises):
                raise ValueError("order promise requires a promise snapshot for every line")
            typed_promises = [promise for promise in line_promises if promise is not None]
            kinds = {promise.kind for promise in typed_promises}
            expected_kind = next(iter(kinds)) if len(kinds) == 1 else "mixed"
            if self.fulfillment_promise.kind != expected_kind:
                raise ValueError("order promise kind does not match its line promises")
            expected_from = max(promise.estimated_from for promise in typed_promises)
            expected_by = max(promise.estimated_by for promise in typed_promises)
            if (
                self.fulfillment_promise.estimated_from != expected_from
                or self.fulfillment_promise.estimated_by != expected_by
            ):
                raise ValueError(
                    "order promise window does not match the accepted no-split promise"
                )
        return self


FulfillmentType = Literal["delivery", "collection"]
FulfillmentStatus = Literal[
    "confirmed",
    "ready_for_delivery",
    "out_for_delivery",
    "delivered",
    "ready_for_collection",
    "collected",
    "cancelled",
]


class StorefrontFulfillmentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    company_id: uuid.UUID
    external_order_id: str = Field(min_length=1, max_length=255)
    revision: int = Field(gt=0)
    fulfillment_type: FulfillmentType
    status: FulfillmentStatus
    fulfillment_promise: Optional[StorefrontOrderPromise] = None
    occurred_at: datetime.datetime


class StorefrontFulfillmentEventList(BaseModel):
    items: list[StorefrontFulfillmentEvent]


class StorefrontFulfillmentEventAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class StorefrontFulfillmentEventAckResponse(BaseModel):
    acknowledged: int


class StorefrontCollectionStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready_for_collection", "collected"]


class StorefrontHandoffLineSnapshot(BaseModel):
    external_line_id: str
    title: str
    sku: str
    quantity: int
    unit_ex_minor_zar: int
    total_minor_zar: int


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
    fulfillment_type: FulfillmentType
    fulfillment_status: FulfillmentStatus
    fulfillment_revision: int
    fulfillment_promise: Optional[StorefrontOrderPromise] = None
    lines: list[StorefrontHandoffLineSnapshot] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime


class StorefrontHandoffListResponse(BaseModel):
    items: list[StorefrontHandoffResponse]


class StorefrontRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: uuid.UUID
    amount_minor: Optional[int] = Field(default=None, gt=0)
    selected_lines: Optional[list["StorefrontRefundLineSelection"]] = Field(
        default=None, min_length=1, max_length=100
    )
    cancel_order: bool = False

    @model_validator(mode="after")
    def require_one_refund_selection(self) -> StorefrontRefundRequest:
        if (self.amount_minor is None) == (self.selected_lines is None):
            raise ValueError("Provide exactly one of amount_minor or selected_lines")
        if self.selected_lines is not None:
            line_ids = [line.external_line_id for line in self.selected_lines]
            if len(set(line_ids)) != len(line_ids):
                raise ValueError("Selected Storefront line identities must be unique")
        return self


class StorefrontRefundLineSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_line_id: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0, le=10000)


class StorefrontRefundResponse(BaseModel):
    id: uuid.UUID
    handoff_id: Optional[uuid.UUID]
    amount_minor: int
    provider_amount_minor: Optional[int] = None
    currency_code: str
    allocation: dict[str, int]
    selected_lines: dict[str, int] = Field(default_factory=dict)
    cancel_order: bool
    status: Literal[
        "requested", "dispatching", "unknown", "pending", "succeeded", "failed", "needs_review"
    ]
    provider_outcome: Optional[Literal["succeeded", "pending", "failed", "unknown"]] = None
    provider_refund_id: Optional[str] = None
    provider_result_code: Optional[str] = None
    failure_code: Optional[str] = None
    signature_verified: bool
    financial_journal_id: Optional[uuid.UUID] = None
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None


class StorefrontRefundLineBalance(BaseModel):
    external_line_id: str
    title: str
    sku: str
    original_quantity: int
    remaining_quantity: int
    original_amount_minor: int
    remaining_amount_minor: int


class StorefrontRefundStatusResponse(BaseModel):
    captured_amount_minor: int
    confirmed_refund_minor: int
    reserved_refund_minor: int
    available_refund_minor: int
    invoice_id: Optional[uuid.UUID]
    invoice_refund_eligible: bool = False
    invoice_refund_available_minor: int = 0
    sales_order_amount_paid: str
    line_balances: list[StorefrontRefundLineBalance] = Field(default_factory=list)
    items: list[StorefrontRefundResponse]


class StorefrontRefundCommand(BaseModel):
    request_id: uuid.UUID
    handoff_id: uuid.UUID
    external_order_id: str
    original_transaction_id: str
    amount_minor: int
    currency_code: str
    cancel_order: bool
    allocation: dict[str, int]
    status: Literal["requested", "dispatching", "unknown", "pending"]


class StorefrontRefundCommandList(BaseModel):
    items: list[StorefrontRefundCommand]


class StorefrontRefundDispatchOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["dispatching", "unknown", "pending"]
    failure_code: Optional[str] = Field(default=None, max_length=64)


class StorefrontRefundProviderEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: Optional[uuid.UUID] = None
    provider_refund_id: str = Field(min_length=1, max_length=128)
    webhook_id: Optional[str] = Field(default=None, max_length=200)
    event_source: Literal["webhook", "response"]
    referenced_capture_id: str = Field(min_length=1, max_length=128)
    event_timestamp: datetime.datetime
    amount_minor: int = Field(gt=0)
    currency_code: Literal["ZAR"]
    result_code: str = Field(min_length=1, max_length=32)
    outcome: Literal["succeeded", "pending", "failed", "unknown"]
    canonical_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    signature_verified: bool

    @field_validator("event_timestamp", mode="after")
    @classmethod
    def normalize_event_timestamp(cls, value: datetime.datetime) -> datetime.datetime:
        if value.tzinfo is None:
            return value
        offset = value.utcoffset()
        if offset is None:
            return value.replace(tzinfo=None)
        return (value - offset).replace(tzinfo=None)


class StorefrontRefundProviderEventResponse(BaseModel):
    status: Literal["succeeded", "pending", "failed", "needs_review"]
    provider_outcome: Literal["succeeded", "pending", "failed", "unknown"]
    resolution_code: Optional[str] = None
    request_id: Optional[uuid.UUID] = None
    external_order_id: Optional[str] = None
    handoff_id: Optional[uuid.UUID] = None
    amount_minor: int
    currency_code: str = "ZAR"
    provider_refund_id: str
    duplicate: bool


class StorefrontOrderStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_order_ids: list[str] = Field(min_length=1, max_length=500)

    @field_validator("external_order_ids")
    @classmethod
    def bounded_unique_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate external order identity")
        if any(not value.strip() or len(value) > 255 for value in values):
            raise ValueError("external order identities must contain 1 to 255 characters")
        return values


class StorefrontOrderStatusItem(BaseModel):
    external_order_id: str
    status: Literal["imported", "missing", "stock_conflict", "failed"]


class StorefrontOrderStatusResponse(BaseModel):
    items: list[StorefrontOrderStatusItem]
