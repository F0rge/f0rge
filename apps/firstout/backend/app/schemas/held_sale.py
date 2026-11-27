from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.invoice import DocumentNote

MAX_HELD_LINES = 100
MAX_HELD_NOTE_LENGTH = 500


class HeldSaleLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: uuid.UUID
    qty: int = Field(gt=0, le=999_999)
    discount_percent: Decimal = Field(
        default=Decimal(0), ge=0, le=100, max_digits=7, decimal_places=4
    )


def _check_basket_lines(lines: list[HeldSaleLineCreate], linked: dict[uuid.UUID, uuid.UUID]):
    skus = {line.sku_id for line in lines}
    if len(skus) != len(lines):
        raise ValueError("A basket can contain each SKU only once")
    if not linked.keys() <= skus:
        raise ValueError("Linked picks must correspond to lines in the basket")
    if len(set(linked.values())) != len(linked):
        raise ValueError("A pick cannot be linked to multiple lines")


class TillBasketUpdate(BaseModel):
    """Whole-basket replace; an empty line list is a valid open basket."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    operation_id: uuid.UUID
    customer_id: Optional[uuid.UUID] = None
    note: Optional[str] = Field(default=None, max_length=MAX_HELD_NOTE_LENGTH)
    note_printed: DocumentNote = None
    note_internal: DocumentNote = None
    sales_staff_id: Optional[uuid.UUID] = None
    quote_id: Optional[uuid.UUID] = None
    pick_id: Optional[uuid.UUID] = None
    linked_pick_ids: dict[uuid.UUID, uuid.UUID] = Field(
        default_factory=dict, max_length=MAX_HELD_LINES
    )
    lines: list[HeldSaleLineCreate] = Field(default_factory=list, max_length=MAX_HELD_LINES)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: Optional[str]) -> Optional[str]:
        return (value or "").strip() or None

    @model_validator(mode="after")
    def validate_basket(self) -> TillBasketUpdate:
        _check_basket_lines(self.lines, self.linked_pick_ids)
        return self


class TillBasketLine(HeldSaleLineCreate):
    # A stored line may carry kept_qty (a held quantity kept against the sale quantity
    # rule); it stays server-side, so clients never send or see it.
    model_config = ConfigDict(extra="ignore")


class TillBasket(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    note: Optional[str]
    note_printed: Optional[str] = None
    note_internal: Optional[str] = None
    sales_staff_id: Optional[uuid.UUID] = None
    quote_id: Optional[uuid.UUID] = None
    pick_id: Optional[uuid.UUID]
    linked_pick_ids: dict[uuid.UUID, uuid.UUID]
    lines: list[TillBasketLine]
    version: int
    updated_at: datetime.datetime
    # While it has lines: when the sale (and its reservations) lapse unless changed.
    expires_at: Optional[datetime.datetime] = None
    # Set when the basket was last emptied by expiry, so the till can say so.
    expired_at: Optional[datetime.datetime] = None


class HeldSaleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    location_id: uuid.UUID
    customer_id: Optional[uuid.UUID] = None
    lines: list[HeldSaleLineCreate] = Field(min_length=1, max_length=MAX_HELD_LINES)
    pick_id: Optional[uuid.UUID] = None
    linked_pick_ids: dict[uuid.UUID, uuid.UUID] = Field(
        default_factory=dict, max_length=MAX_HELD_LINES
    )
    note: Optional[str] = Field(default=None, max_length=MAX_HELD_NOTE_LENGTH)
    note_printed: DocumentNote = None
    note_internal: DocumentNote = None
    sales_staff_id: Optional[uuid.UUID] = None
    quote_id: Optional[uuid.UUID] = None
    # When set, the caller's server basket is emptied in the same transaction.
    basket_id: Optional[uuid.UUID] = None

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: Optional[str]) -> Optional[str]:
        return (value or "").strip() or None

    @model_validator(mode="after")
    def validate_basket(self) -> HeldSaleCreate:
        _check_basket_lines(self.lines, self.linked_pick_ids)
        return self


class HeldSaleNoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: uuid.UUID
    version: int = Field(ge=1)
    note: Optional[str] = Field(max_length=MAX_HELD_NOTE_LENGTH)


class HeldSaleResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: uuid.UUID
    operation_id: uuid.UUID
    version: int = Field(ge=1)
    current: Optional[HeldSaleCreate] = None
    # When set, the resumed contents are written into this server basket.
    basket_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def validate_location(self) -> HeldSaleResume:
        if self.current is not None and self.current.location_id != self.location_id:
            raise ValueError("Both baskets must be in the same showroom")
        return self


class HeldSaleResumeResult(BaseModel):
    resumed_id: uuid.UUID
    held_current_id: Optional[uuid.UUID] = None
    basket: Optional[TillBasket] = None


class HeldSaleDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: uuid.UUID
    ids: list[uuid.UUID]
    all: bool = False

    @model_validator(mode="after")
    def validate_ids(self) -> HeldSaleDelete:
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("Held-sale IDs must be unique")
        if not self.ids and not self.all:
            raise ValueError("Choose at least one held sale to delete")
        return self


class HeldSaleDeleteResult(BaseModel):
    deleted_count: int


class HeldSaleLine(HeldSaleLineCreate):
    sku_code: str
    sku_name: str
    estimated_total_inc_vat: Optional[Decimal] = None
    # The held quantity, when it met the SKU's selling rule (or the holder could break
    # it) at the moment of holding: completing the sale keeps it even if the rule tightens.
    kept_qty: Optional[int] = None


class HeldSale(BaseModel):
    id: uuid.UUID
    reference: str
    location_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    customer_name: str
    held_by_name: str
    held_at: datetime.datetime
    expires_at: datetime.datetime
    version: int
    note: Optional[str]
    note_printed: Optional[str] = None
    note_internal: Optional[str] = None
    sales_staff_id: Optional[uuid.UUID] = None
    quote_id: Optional[uuid.UUID] = None
    estimated_total_inc_vat: Optional[Decimal]
    pick_id: Optional[uuid.UUID]
    linked_pick_ids: dict[uuid.UUID, uuid.UUID]
    lines: list[HeldSaleLine]
