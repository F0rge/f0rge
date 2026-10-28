"""Supplier-facing purchase order PDF.

Uses the same ReportLab canvas, seller block, and logo helper as the packing sheet.
This document is what we send the factory. It shows their model code and the price
we are ordering at. It does not show our landed cost, selling prices, or margins.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.invoice_pdf import (
    SELLER_ADDRESS,
    SELLER_NAME,
    SELLER_VAT_NUMBER,
    SellerDetails,
    draw_seller_logo,
)

DRAFT_BANNER = "DRAFT – not approved"


@dataclass(frozen=True)
class PurchaseOrderPdfLine:
    supplier_code: Optional[str]
    description: str
    our_ref: Optional[str]
    fabric: Optional[str]
    notes: Optional[str]
    qty: int
    unit_price: Decimal


def _money(amount: Decimal) -> str:
    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{quantized:.2f}"


def _line_total(line: PurchaseOrderPdfLine) -> Decimal:
    return (Decimal(line.qty) * line.unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_purchase_order_pdf(
    *,
    po_number: str,
    po_date: str,
    status_label: str,
    draft: bool,
    supplier_name: str,
    supplier_ref: Optional[str],
    currency: str,
    notes: Optional[str],
    lines: list[PurchaseOrderPdfLine],
    seller: Optional[SellerDetails] = None,
) -> bytes:
    seller_details = seller or SellerDetails(
        name=SELLER_NAME,
        address=SELLER_ADDRESS,
        vat_number=SELLER_VAT_NUMBER,
        vat_percent_label="15%",
    )

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    x = 20 * mm
    y = height - 22 * mm

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(x, y, "Purchase Order")
    draw_seller_logo(pdf, seller_details, page_width=width, anchor_y=y)
    y -= 8 * mm

    if draft:
        pdf.setFillColorRGB(0.7, 0.1, 0.1)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(x, y, DRAFT_BANNER)
        pdf.setFillColorRGB(0, 0, 0)
        y -= 8 * mm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x, y, seller_details.name)
    y -= 5 * mm
    pdf.setFont("Helvetica", 10)
    for part in (seller_details.address, f"VAT No: {seller_details.vat_number}"):
        pdf.drawString(x, y, part)
        y -= 5 * mm
    y -= 3 * mm

    pdf.setFont("Helvetica", 10)
    header_lines = [
        f"Supplier: {supplier_name}",
        f"PO number: {po_number}",
        f"Date: {po_date}",
        f"Supplier reference: {supplier_ref or '—'}",
        f"Status: {status_label}",
        f"Currency: {currency}",
    ]
    for text in header_lines:
        pdf.drawString(x, y, text)
        y -= 5 * mm
    y -= 4 * mm

    grand = Decimal("0.00")
    for line in lines:
        y = _ensure_room(pdf, y, height, needed=42 * mm)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(x, y, f"Supplier code: {line.supplier_code or '—'}")
        y -= 6 * mm
        pdf.setFont("Helvetica", 10)
        y = _draw_wrapped(pdf, f"Description: {line.description}", x, y, width - 40 * mm)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(x, y, f"Our ref: {line.our_ref or '—'}")
        y -= 5 * mm
        pdf.setFont("Helvetica", 10)
        if line.fabric:
            pdf.drawString(x, y, f"Fabric / finish: {line.fabric}")
            y -= 5 * mm
        if line.notes:
            y = _draw_wrapped(pdf, f"Notes: {line.notes}", x, y, width - 40 * mm)
        total = _line_total(line)
        grand += total
        pdf.drawString(
            x,
            y,
            f"Qty: {line.qty}    Unit price: {currency} {_money(line.unit_price)}    "
            f"Line total: {currency} {_money(total)}",
        )
        y -= 8 * mm

    y = _ensure_room(pdf, y, height, needed=20 * mm)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(x, y, f"Grand total: {currency} {_money(grand)}")
    y -= 8 * mm
    if notes:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x, y, "Notes")
        y -= 5 * mm
        pdf.setFont("Helvetica", 10)
        _draw_wrapped(pdf, notes, x, y, width - 40 * mm)

    pdf.save()
    return buffer.getvalue()


def _ensure_room(pdf: canvas.Canvas, y: float, height: float, needed: float) -> float:
    if y >= needed:
        return y
    pdf.showPage()
    pdf.setFillColorRGB(0, 0, 0)
    return height - 22 * mm


def _draw_wrapped(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
) -> float:
    font = "Helvetica"
    size = 10
    pdf.setFont(font, size)
    words = text.split()
    if not words:
        return y
    line = words[0]
    for word in words[1:]:
        trial = f"{line} {word}"
        if pdf.stringWidth(trial, font, size) <= max_width:
            line = trial
            continue
        pdf.drawString(x, y, line)
        y -= 5 * mm
        line = word
    pdf.drawString(x, y, line)
    return y - 5 * mm
