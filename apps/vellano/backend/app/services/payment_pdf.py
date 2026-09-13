from __future__ import annotations

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


def build_payment_receipt_pdf(
    payment_number: str,
    direction_label: str,
    paid_on: str,
    amount: str,
    currency: str,
    amount_zar: str,
    tender: Optional[str],
    linked_document: Optional[str],
    seller: Optional[SellerDetails] = None,
) -> bytes:
    from io import BytesIO

    seller_details = seller or SellerDetails(
        name=SELLER_NAME,
        address=SELLER_ADDRESS,
        vat_number=SELLER_VAT_NUMBER,
        vat_percent_label="15%",
    )

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
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
    draw_seller_logo(pdf, seller_details, page_width=width, anchor_y=y)
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, seller_details.name)
    y -= 5 * mm
    pdf.drawString(25 * mm, y, seller_details.address)
    y -= 5 * mm
    pdf.drawString(25 * mm, y, f"VAT No: {seller_details.vat_number}")
    y -= 5 * mm
    if seller_details.bank_name and seller_details.bank_account:
        pdf.drawString(
            25 * mm,
            y,
            f"Bank: {seller_details.bank_name} — {seller_details.bank_account}",
        )
        y -= 5 * mm
        if seller_details.bank_branch_code:
            pdf.drawString(25 * mm, y, f"Branch: {seller_details.bank_branch_code}")
            y -= 5 * mm
    y -= 7 * mm

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
