from __future__ import annotations

from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

SELLER_NAME = "Vellano"
SELLER_ADDRESS = "Kramerville, Johannesburg, South Africa"
SELLER_VAT_NUMBER = "4123456789"


def build_tax_invoice_pdf(
    invoice_number: str,
    issue_date: str,
    customer_name: str,
    customer_vat: Optional[str],
    customer_address: Optional[str],
    lines: list[tuple[str, int, str, str, str, str]],
    subtotal_ex_vat: str,
    vat_amount: str,
    total_inc_vat: str,
) -> bytes:
    """Each line: description, qty, unit_ex_vat, ex_vat, vat_amount, inc_vat."""
    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(25 * mm, y, "Tax Invoice")
    y -= 10 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, f"Invoice No: {invoice_number}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Date: {issue_date}")
    y -= 12 * mm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(25 * mm, y, "Seller")
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, SELLER_NAME)
    y -= 5 * mm
    pdf.drawString(25 * mm, y, SELLER_ADDRESS)
    y -= 5 * mm
    pdf.drawString(25 * mm, y, f"VAT No: {SELLER_VAT_NUMBER}")
    y -= 12 * mm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(25 * mm, y, "Buyer")
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, customer_name)
    y -= 5 * mm
    if customer_address:
        pdf.drawString(25 * mm, y, customer_address)
        y -= 5 * mm
    if customer_vat:
        pdf.drawString(25 * mm, y, f"VAT No: {customer_vat}")
        y -= 5 * mm
    y -= 8 * mm

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(25 * mm, y, "Description")
    pdf.drawString(110 * mm, y, "Ex-VAT")
    pdf.drawString(135 * mm, y, "VAT")
    pdf.drawString(160 * mm, y, "Inc-VAT")
    y -= 6 * mm
    pdf.setFont("Helvetica", 9)

    for description, qty, unit_ex, ex_vat, line_vat, inc_vat in lines:
        if y < 40 * mm:
            pdf.showPage()
            y = height - 25 * mm
            pdf.setFont("Helvetica", 9)
        pdf.drawString(25 * mm, y, f"{description} (x{qty} @ {unit_ex})")
        pdf.drawString(110 * mm, y, ex_vat)
        pdf.drawString(135 * mm, y, line_vat)
        pdf.drawString(160 * mm, y, inc_vat)
        y -= 6 * mm

    y -= 8 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(110 * mm, y, f"Subtotal ex-VAT: {subtotal_ex_vat}")
    y -= 6 * mm
    pdf.drawString(110 * mm, y, f"VAT (15%): {vat_amount}")
    y -= 6 * mm
    pdf.drawString(110 * mm, y, f"Total inc-VAT: {total_inc_vat}")

    pdf.save()
    return buffer.getvalue()
