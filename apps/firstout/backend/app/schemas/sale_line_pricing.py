from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SaleLinePrice(BaseModel):
    """One priced line of a sale document, exactly as saving it would store it."""

    # None for a free-text books line.
    sku_id: Optional[uuid.UUID] = None
    qty: int
    discount_percent: Decimal
    # The unit the line charges before its discount: the resolved price, a kept saved
    # price or a price override.
    unit_ex_vat: Decimal
    unit_inc_vat: Decimal
    # What Sale line pricing resolved for the SKU; None for a free-text line.
    resolved_unit_ex_vat: Optional[Decimal] = None
    before_discount_ex_vat: Decimal
    ex_vat: Decimal
    vat_amount: Decimal
    inc_vat: Decimal
    # price_list, stockist, wholesale, decorator, retail, retail_fallback, saved,
    # override or manual (free text).
    source: str
    price_warning: Optional[str] = None
    suspect_price_warning: Optional[str] = None
    # The permission that refuses this line's discount or price override, if any:
    # till.discount, users.manage (above the Discount cap), sales.price_override, or
    # quantity_rule (the quantity breaks the SKU's selling rule).
    blocked_by: Optional[str] = None
    # The plain message when the quantity breaks the SKU's selling rule, e.g. "Oslo dining
    # chair is sold in multiples of 2, minimum 4." Set whether or not the actor may break
    # it: with blocked_by "quantity_rule" it is a refusal; otherwise a sales.price_override
    # holder is breaking a batch and the till shows it as a notice.
    quantity_rule: Optional[str] = None


class SalePricePreview(BaseModel):
    classification: str
    price_list_name: Optional[str]
    prices_include_vat: bool
    # The VAT rate these amounts use (0.15 is 15%); the document stores it (ADR 0003).
    vat_rate: Decimal
    before_discount_ex_vat: Decimal
    before_discount_inc_vat: Decimal
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    # One per request line, in request order.
    lines: list[SaleLinePrice]
    price_revision: str
