from __future__ import annotations

from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.invoice_pdf import SELLER_ADDRESS, SELLER_NAME, SELLER_VAT_NUMBER


def build_payment_receipt_pdf(
    payment_number: str,
    direction_label: str,
    paid_on: str,
    amount: str,
    currency: str,
    amount_zar: str,
    tender: Optional[str],
    linked_document: Optional[str],
) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    height = A4[1]
    y = height - 25 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(25 * mm, y, "Payment Receipt")
    y -= 10 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, f"Receipt No: {payment_number}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Date: {paid_on}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Direction: {direction_label}")
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
    pdf.drawString(25 * mm, y, "Payment")
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, f"Amount: {amount} {currency}")
    y -= 5 * mm
    pdf.drawString(25 * mm, y, f"ZAR: {amount_zar}")
    y -= 5 * mm
    if tender:
        pdf.drawString(25 * mm, y, f"Tender: {tender}")
        y -= 5 * mm
    if linked_document:
        pdf.drawString(25 * mm, y, linked_document)
        y -= 5 * mm

    pdf.save()
    return buffer.getvalue()
