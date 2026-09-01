from __future__ import annotations

from decimal import Decimal
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_packing_sheet_pdf(
    po_number: str,
    lines: list[tuple[str, str, str, str, int, int]],
) -> bytes:
    """Build packing sheet PDF.

    Each line: our_ref, our_barcode, name, fabric, qty, carton_count.
    qty is sellable units. carton_count is a document multiplier only.
    """
    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 30 * mm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30 * mm, y, f"Packing Sheet — {po_number}")
    y -= 15 * mm

    pdf.setFont("Helvetica", 10)
    for our_ref, our_barcode, name, fabric, qty, carton_count in lines:
        if y < 40 * mm:
            pdf.showPage()
            y = height - 30 * mm
            pdf.setFont("Helvetica", 10)

        pdf.drawString(30 * mm, y, f"Ref: {our_ref}")
        y -= 6 * mm
        pdf.drawString(30 * mm, y, f"Barcode: {our_barcode}")
        y -= 6 * mm
        pdf.drawString(30 * mm, y, f"Name: {name}")
        y -= 6 * mm
        pdf.drawString(30 * mm, y, f"Fabric: {fabric}")
        y -= 6 * mm
        pdf.drawString(30 * mm, y, f"Qty: {qty}")
        y -= 6 * mm
        if carton_count > 1:
            pdf.drawString(
                30 * mm,
                y,
                f"Cartons: {qty} \xd7 {carton_count} = {qty * carton_count}",
            )
            y -= 6 * mm
        y -= 4 * mm

    pdf.save()
    return buffer.getvalue()


def convert_bill_to_zar(
    amount: Decimal,
    currency: str,
    fx_to_zar: Decimal,
) -> Decimal:
    if currency.upper() == "ZAR":
        return amount
    return amount * fx_to_zar


def compute_landed_unit_costs(
    lines: list[tuple[int, Decimal]],
    factory_zar: Decimal,
    freight_zar: Decimal,
    clearance_zar: Decimal,
) -> list[Decimal]:
    """Return unit_cost_zar per line. lines: (qty, factory_unit_amount)."""
    total_zar = factory_zar + freight_zar + clearance_zar
    weights = [Decimal(qty) * factory_unit_amount for qty, factory_unit_amount in lines]
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("Total line weight must be positive")

    unit_costs: list[Decimal] = []
    for qty, factory_unit_amount in lines:
        line_weight = Decimal(qty) * factory_unit_amount
        line_share = line_weight / total_weight
        line_landed_zar = line_share * total_zar
        unit_cost = line_landed_zar / Decimal(qty)
        unit_costs.append(unit_cost)
    return unit_costs


def sku_level_unit_cost(
    location_stocks: list[tuple[int, Optional[Decimal]]],
) -> Optional[Decimal]:
    """Weighted average unit cost across locations with on_hand > 0."""
    total_qty = 0
    total_value = Decimal(0)
    for on_hand, unit_cost in location_stocks:
        if on_hand > 0 and unit_cost is not None:
            total_qty += on_hand
            total_value += Decimal(on_hand) * unit_cost
    if total_qty == 0:
        return None
    return total_value / Decimal(total_qty)
