"""Compare a supplier invoice with the purchase order it should match."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from app.services.document_intake.pricing import CENT, money, within_cent


def _label(amount: Decimal, currency: str) -> str:
    shown = money(amount, CENT)
    if currency.upper() == "ZAR":
        return f"R{shown}"
    return f"{shown} {currency.upper()}"


def compare_invoice(
    *,
    currency: str,
    po_currency: str,
    po_lines: list[tuple[uuid.UUID, str, int, Decimal]],
    invoice_lines: list[tuple[int, Optional[uuid.UUID], str, int, Decimal]],
    po_charges: list[tuple[str, Decimal]],
    invoice_charges: list[tuple[str, Decimal]],
    po_vat: Optional[Decimal],
    invoice_vat: Optional[Decimal],
    po_total: Optional[Decimal],
    invoice_total: Optional[Decimal],
) -> tuple[bool, list[str]]:
    """Return whether the invoice matches the order, and plain-English differences.

    ``po_lines`` is (sku_id, our_ref, qty, unit_price).
    ``invoice_lines`` is (line_number, sku_id, description, qty, unit_price).
    Prices are the net unit after discount.
    """
    differences: list[str] = []
    if currency.upper() != po_currency.upper():
        differences.append(
            f"Invoice currency is {currency.upper()}, the order is {po_currency.upper()}."
        )

    remaining: dict[uuid.UUID, tuple[str, int, Decimal]] = {
        sku_id: (our_ref, qty, price) for sku_id, our_ref, qty, price in po_lines
    }
    for line_number, sku_id, description, qty, price in invoice_lines:
        if sku_id is None or sku_id not in remaining:
            differences.append(
                f"Line {line_number}: invoice has {description}, which is not on the order."
            )
            continue
        our_ref, order_qty, order_price = remaining.pop(sku_id)
        if qty != order_qty or not within_cent(price, order_price):
            differences.append(
                f"Line {line_number}: invoice says {qty} units at {_label(price, currency)}, "
                f"order said {order_qty} at {_label(order_price, po_currency)}."
            )

    for our_ref, qty, price in remaining.values():
        differences.append(
            f"The order includes {our_ref}, {qty} at {_label(price, po_currency)}, "
            "and the invoice does not."
        )

    po_charge_map = {_charge_key(name): (name, amount) for name, amount in po_charges}
    seen_charges: set[str] = set()
    for name, amount in invoice_charges:
        key = _charge_key(name)
        seen_charges.add(key)
        current = po_charge_map.get(key)
        if current is None:
            if amount > CENT:
                differences.append(
                    f"Invoice includes {name} {_label(amount, currency)}, "
                    "which is not on the purchase order."
                )
            continue
        _order_name, order_amount = current
        if not within_cent(amount, order_amount):
            differences.append(
                f"Invoice {name} is {_label(amount, currency)}, "
                f"the order said {_label(order_amount, po_currency)}."
            )
    for key, (name, amount) in po_charge_map.items():
        if key not in seen_charges and amount > CENT:
            differences.append(
                f"The order includes {name} {_label(amount, po_currency)}, and the invoice does not."
            )

    po_vat_amount = po_vat or Decimal("0")
    invoice_vat_amount = invoice_vat or Decimal("0")
    if not within_cent(po_vat_amount, invoice_vat_amount):
        differences.append(
            f"VAT on the invoice is {_label(invoice_vat_amount, currency)}, "
            f"the order said {_label(po_vat_amount, po_currency)}."
        )

    if invoice_total is None:
        differences.append("The invoice total was not read.")
    elif po_total is not None and not within_cent(invoice_total, po_total):
        differences.append(
            f"Invoice total is {_label(invoice_total, currency)}, "
            f"the order said {_label(po_total, po_currency)}."
        )

    return (len(differences) == 0, differences)


def discount_differences(
    pairs: list[tuple[int, Optional[Decimal], Optional[Decimal]]],
) -> list[str]:
    """Flag a discount only when both the invoice and the order recorded one."""
    notes: list[str] = []
    for line_number, invoice_discount, order_discount in pairs:
        if invoice_discount is None or order_discount is None:
            continue
        if not within_cent(invoice_discount, order_discount):
            notes.append(
                f"Line {line_number}: invoice discount is {money(invoice_discount, CENT)}%, "
                f"the order said {money(order_discount, CENT)}%."
            )
    return notes


def _charge_key(name: str) -> str:
    return " ".join(name.lower().split())
