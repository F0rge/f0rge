from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.team_settings import (
    DEFAULT_ADDRESS,
    DEFAULT_LEGAL_NAME,
    DEFAULT_VAT_NUMBER,
    TeamSettings,
)

SELLER_NAME = DEFAULT_LEGAL_NAME
SELLER_ADDRESS = DEFAULT_ADDRESS
SELLER_VAT_NUMBER = DEFAULT_VAT_NUMBER


@dataclass(frozen=True)
class SellerDetails:
    name: str
    address: str
    vat_number: str
    vat_percent_label: str
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_branch_code: Optional[str] = None
    logo_bytes: Optional[bytes] = None


def seller_details_from_settings(
    settings: TeamSettings,
    *,
    logo_bytes: Optional[bytes] = None,
) -> SellerDetails:
    vat_pct = (settings.vat_rate * Decimal("100")).quantize(Decimal("0.01"))
    return SellerDetails(
        name=settings.legal_name,
        address=settings.address,
        vat_number=settings.vat_number,
        vat_percent_label=f"{vat_pct}%",
        bank_name=settings.bank_name,
        bank_account=settings.bank_account,
        bank_branch_code=settings.bank_branch_code,
        logo_bytes=logo_bytes,
    )


def draw_seller_logo(
    pdf: canvas.Canvas,
    seller_details: SellerDetails,
    *,
    page_width: float,
    anchor_y: float,
) -> None:
    if not seller_details.logo_bytes:
        return
    try:
        from io import BytesIO

        from reportlab.lib.utils import ImageReader

        image = ImageReader(BytesIO(seller_details.logo_bytes))
        img_w, img_h = image.getSize()
        max_w = 35 * mm
        max_h = 20 * mm
        scale = min(max_w / img_w, max_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        x = page_width - 25 * mm - draw_w
        y = anchor_y - draw_h + 2 * mm
        pdf.drawImage(image, x, y, width=draw_w, height=draw_h, mask="auto")
    except Exception:
        return


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
    title: str = "Tax Invoice",
    original_invoice_number: Optional[str] = None,
    credit_reason: Optional[str] = None,
    seller: Optional[SellerDetails] = None,
    due_date: Optional[str] = None,
) -> bytes:
    """Each line: description, qty, unit_ex_vat, ex_vat, vat_amount, inc_vat."""
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
    pdf.drawString(25 * mm, y, title)
    y -= 10 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, f"Invoice No: {invoice_number}")
    y -= 6 * mm
    if original_invoice_number:
        pdf.drawString(25 * mm, y, f"Original invoice: {original_invoice_number}")
        y -= 6 * mm
    if credit_reason:
        pdf.drawString(25 * mm, y, f"Reason: {credit_reason}")
        y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Date: {issue_date}")
    y -= 6 * mm
    if due_date:
        pdf.drawString(25 * mm, y, f"Due date: {due_date}")
        y -= 6 * mm
    y -= 6 * mm

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
    pdf.drawString(
        110 * mm,
        y,
        f"VAT ({seller_details.vat_percent_label}): {vat_amount}",
    )
    y -= 6 * mm
    pdf.drawString(110 * mm, y, f"Total inc-VAT: {total_inc_vat}")

    pdf.save()
    return buffer.getvalue()
