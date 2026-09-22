from __future__ import annotations

from io import BytesIO
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.invoice_pdf import SellerDetails, draw_seller_logo


def build_layby_pdf(
    *,
    layby_number: str,
    customer_name: str,
    due_date: str,
    lines: list[tuple[str, int]],
    amount_paid: str,
    balance: str,
    total_inc_vat: str,
    seller: SellerDetails,
    status: Optional[str] = None,
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(25 * mm, y, "Layby")
    y -= 10 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, f"Number: {layby_number}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Due date: {due_date}")
    y -= 6 * mm
    if status:
        pdf.drawString(25 * mm, y, f"Status: {status}")
        y -= 6 * mm
    y -= 6 * mm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(25 * mm, y, "Seller")
    draw_seller_logo(pdf, seller, page_width=width, anchor_y=y)
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, seller.name)
    y -= 5 * mm
    pdf.drawString(25 * mm, y, seller.address)
    y -= 8 * mm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(25 * mm, y, "Customer")
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, customer_name)
    y -= 10 * mm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(25 * mm, y, "Items")
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    for name, qty in lines:
        if y < 40 * mm:
            pdf.showPage()
            y = height - 25 * mm
            pdf.setFont("Helvetica", 10)
        pdf.drawString(25 * mm, y, f"{name} × {qty}")
        y -= 6 * mm

    y -= 8 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(25 * mm, y, f"Total inc-VAT: {total_inc_vat}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Paid: {amount_paid}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Balance: {balance}")

    pdf.save()
    return buffer.getvalue()
