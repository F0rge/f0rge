"""Cents-safe settlement status and partial payment amounts."""

from __future__ import annotations

import enum
from decimal import Decimal, ROUND_HALF_UP

from f0rge_core.exceptions import ValidationError

CENT = Decimal("0.01")


class SettlementStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


def cents(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def assert_payment_cents(amount: Decimal) -> Decimal:
    """Reject anything that is not a positive amount in whole cents."""
    if amount != cents(amount):
        raise ValidationError("Payment amount must be in cents.")
    quantized = cents(amount)
    if quantized <= 0:
        raise ValidationError("Payment amount must be more than zero.")
    return quantized


def settlement_status(amount_paid: Decimal, total: Decimal) -> SettlementStatus:
    paid = cents(amount_paid or Decimal(0))
    owing = cents(total or Decimal(0))
    if paid <= 0:
        return SettlementStatus.UNPAID
    if paid >= owing:
        return SettlementStatus.PAID
    return SettlementStatus.PARTIALLY_PAID


def bill_settlement_status(
    amount_paid_foreign: Decimal,
    amount_foreign: Decimal,
    amount_paid_zar: Decimal,
    amount_zar: Decimal,
) -> SettlementStatus:
    foreign = settlement_status(amount_paid_foreign, amount_foreign)
    zar = settlement_status(amount_paid_zar, amount_zar)
    if foreign == SettlementStatus.PAID and zar == SettlementStatus.PAID:
        return SettlementStatus.PAID
    if foreign == SettlementStatus.UNPAID and zar == SettlementStatus.UNPAID:
        return SettlementStatus.UNPAID
    return SettlementStatus.PARTIALLY_PAID


def format_money(amount: Decimal, currency: str) -> str:
    formatted = f"{cents(amount):,.2f}"
    if currency.upper() == "ZAR":
        return f"R {formatted}"
    return f"{currency.upper()} {formatted}"


def overpayment_message(remaining: Decimal, currency: str, document_number: str) -> str:
    shown = format_money(remaining, currency)
    return f"Payment is more than the {shown} still owing on {document_number}."


def booked_portion(
    *,
    amount: Decimal,
    amount_foreign: Decimal,
    amount_zar: Decimal,
    amount_paid_foreign: Decimal,
    amount_paid_zar: Decimal,
) -> Decimal:
    """ZAR of the booked bill cleared by this foreign (or ZAR) payment.

    The final slice takes whatever booked ZAR is left so cents do not drift.
    """
    remaining_foreign = cents(amount_foreign - amount_paid_foreign)
    remaining_zar = cents(amount_zar - amount_paid_zar)
    if amount == remaining_foreign:
        return remaining_zar
    if amount_foreign == 0:
        return Decimal(0)
    portion = cents(amount_zar * amount / amount_foreign)
    if portion > remaining_zar:
        return remaining_zar
    return portion
