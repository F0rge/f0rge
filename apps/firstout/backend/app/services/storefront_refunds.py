from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from f0rge_core.exceptions import ValidationError


def storefront_line_values(payload: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    lines = payload.get("lines")
    totals = payload.get("totals")
    if not isinstance(lines, list) or not isinstance(totals, Mapping):
        raise ValidationError("Storefront paid snapshot is incomplete")

    values: dict[str, int] = {}
    quantities: dict[str, int] = {}
    for line in lines:
        if not isinstance(line, Mapping):
            raise ValidationError("Storefront paid snapshot line is invalid")
        line_id = line.get("external_line_id")
        gross = line.get("total_minor_zar")
        quantity = line.get("quantity")
        if (
            not isinstance(line_id, str)
            or not line_id
            or line_id == "delivery"
            or isinstance(gross, bool)
            or not isinstance(gross, int)
            or gross < 0
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
            or line_id in values
        ):
            raise ValidationError("Storefront paid snapshot line is invalid")
        values[line_id] = gross
        quantities[line_id] = quantity

    delivery_gross = totals.get("delivery_total_minor_zar")
    captured_gross = totals.get("total_minor_zar")
    if (
        isinstance(delivery_gross, bool)
        or not isinstance(delivery_gross, int)
        or delivery_gross < 0
        or isinstance(captured_gross, bool)
        or not isinstance(captured_gross, int)
        or captured_gross <= 0
    ):
        raise ValidationError("Storefront paid snapshot totals are invalid")
    if delivery_gross:
        values["delivery"] = delivery_gross
    if sum(values.values()) != captured_gross:
        raise ValidationError("Refund amount does not match the immutable paid snapshot")
    return values, quantities


def allocate_refund_cents(
    payload: Mapping[str, Any],
    amount_minor: int,
    already_allocated: Optional[Mapping[str, int]] = None,
) -> dict[str, int]:
    """Allocate a refund over the immutable paid snapshot using largest remainders.

    Each line's gross captured cents, plus delivery gross cents, is the weight.
    Floors are assigned first; leftover cents go by descending fractional
    remainder, then lexicographically by external line ID (delivery sorts last).
    This allocation is an audit explanation only: it never changes stock.
    """
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int) or amount_minor <= 0:
        raise ValidationError("Refund amount must be a positive whole number of cents")

    values, _ = storefront_line_values(payload)
    previous = dict(already_allocated or {})
    if any(value < 0 for value in previous.values()):
        raise ValidationError("Previous Storefront refund allocation is invalid")
    remaining = {key: gross - previous.get(key, 0) for key, gross in values.items()}
    if any(value < 0 for value in remaining.values()):
        raise ValidationError("Previous Storefront refunds exceed the immutable paid snapshot")
    available = sum(remaining.values())
    if amount_minor > available:
        raise ValidationError("Refund amount exceeds the remaining paid snapshot balance")
    weights = {key: value for key, value in remaining.items() if value > 0}
    if not weights:
        raise ValidationError("Storefront refund balance is exhausted")

    allocation: dict[str, int] = {}
    remainders: list[tuple[int, str]] = []
    assigned = 0
    for key, weight in weights.items():
        cents, remainder = divmod(amount_minor * weight, available)
        allocation[key] = cents
        assigned += cents
        remainders.append((remainder, key))

    # Largest remainder is deterministic even when fractional cents tie.
    remainders.sort(key=lambda item: (-item[0], item[1] == "delivery", item[1]))
    for _, key in remainders[: amount_minor - assigned]:
        allocation[key] += 1
    return allocation


def allocate_selected_line_refund(
    payload: Mapping[str, Any],
    selected_lines: Mapping[str, int],
    already_allocated: Optional[Mapping[str, int]] = None,
    already_selected: Optional[Mapping[str, int]] = None,
) -> tuple[int, dict[str, int]]:
    """Price selected quantities from the immutable snapshot and remaining line balance."""
    values, quantities = storefront_line_values(payload)
    previous_amounts = dict(already_allocated or {})
    previous_quantities = dict(already_selected or {})
    allocation: dict[str, int] = {}
    amount_minor = 0
    for line_id, quantity in selected_lines.items():
        if line_id not in quantities:
            raise ValidationError("Selected Storefront line does not belong to this order")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError("Selected Storefront line quantity must be positive")
        remaining_qty = quantities[line_id] - previous_quantities.get(line_id, 0)
        remaining_value = values[line_id] - previous_amounts.get(line_id, 0)
        if quantity > remaining_qty or remaining_value < 0:
            raise ValidationError("Selected Storefront line exceeds its remaining balance")
        if remaining_qty <= 0:
            raise ValidationError("Selected Storefront line quantity is exhausted")
        base, remainder = divmod(remaining_value, remaining_qty)
        line_amount = base * quantity + min(quantity, remainder)
        if line_amount <= 0:
            raise ValidationError("Selected Storefront line has no refundable value remaining")
        allocation[line_id] = line_amount
        amount_minor += line_amount
    if amount_minor <= 0:
        raise ValidationError("Selected Storefront lines must have a positive refundable value")
    return amount_minor, allocation
