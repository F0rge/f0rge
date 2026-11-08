"""Paginated supplier-facing purchase orders; never internal costs or selling prices."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    LongTable,
    PageTemplate,
    Paragraph,
    Spacer,
    TableStyle,
)

from app.services.invoice_pdf import (
    SELLER_ADDRESS,
    SELLER_NAME,
    SELLER_VAT_NUMBER,
    SellerDetails,
    draw_seller_logo,
)

DRAFT_BANNER = "DRAFT - not approved"


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


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    # User text is always literal. Only this controlled newline tag is markup;
    # caller strings must never become ReportLab links, images or XML elements.
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


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
    width, height = A4
    margin = 20 * mm
    body_width = width - 2 * margin
    top = 47 * mm
    document = BaseDocTemplate(buffer, pagesize=A4, title="Purchase Order")
    frame = Frame(
        margin,
        margin,
        body_width,
        height - top - margin,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )

    def page_header_footer(pdf, doc):
        pdf.saveState()
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 16)
        y = height - 22 * mm
        pdf.drawString(margin, y, "Purchase Order")
        draw_seller_logo(pdf, seller_details, page_width=width, anchor_y=y)
        if draft:
            pdf.setFillColorRGB(0.7, 0.1, 0.1)
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(margin, y - 8 * mm, DRAFT_BANNER)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(margin, 12 * mm, "Supplier purchase order")
        pdf.drawRightString(width - margin, 12 * mm, f"Page {doc.page}")
        pdf.restoreState()

    document.addPageTemplates(
        PageTemplate(id="purchase-order", frames=[frame], onPage=page_header_footer)
    )
    body = ParagraphStyle(
        "po-body", fontName="Helvetica", fontSize=10, leading=14, splitLongWords=True
    )
    small = ParagraphStyle("po-small", parent=body, fontSize=9, leading=13)
    heading = ParagraphStyle(
        "po-heading", parent=body, fontName="Helvetica-Bold", fontSize=12, leading=16
    )
    label = ParagraphStyle("po-label", parent=body, fontName="Helvetica-Bold", keepWithNext=True)
    story = [
        _paragraph(seller_details.name, heading),
        _paragraph(seller_details.address, body),
        _paragraph(f"VAT No: {seller_details.vat_number}", body),
        Spacer(1, 4 * mm),
    ]
    for text in (
        f"Supplier: {supplier_name}",
        f"PO number: {po_number}",
        f"Date: {po_date}",
        f"Supplier reference: {supplier_ref or '-'}",
        f"Status: {status_label}",
        f"Currency: {currency}",
    ):
        story.append(_paragraph(text, body))
    story.append(Spacer(1, 4 * mm))

    grand = Decimal("0.00")
    for number, line in enumerate(lines, start=1):
        total = _line_total(line)
        grand += total
        rows = [
            [_paragraph(f"Line {number} | Supplier code: {line.supplier_code or '-'}", heading)],
            [_paragraph(f"Description: {line.description}", body)],
            [_paragraph(f"Our ref: {line.our_ref or '-'}", small)],
        ]
        if line.fabric:
            rows.append([_paragraph(f"Fabric / finish: {line.fabric}", body)])
        if line.notes:
            rows.append([_paragraph(f"Notes: {line.notes}", body)])
        rows.append(
            [
                _paragraph(
                    f"Qty: {line.qty}    Unit price: {currency} {_money(line.unit_price)}    Line total: {currency} {_money(total)}",
                    body,
                )
            ]
        )
        # A single cell may contain pages of instructions. Split inside the row,
        # repeating the model-code context rather than dropping or clipping text.
        table = LongTable(
            rows,
            colWidths=[body_width],
            repeatRows=1,
            splitByRow=1,
            splitInRow=1,
            hAlign="LEFT",
            spaceAfter=4 * mm,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f4")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    story.extend(
        [_paragraph(f"Grand total: {currency} {_money(grand)}", heading), Spacer(1, 4 * mm)]
    )
    if notes:
        story.extend([_paragraph("Order notes", label), _paragraph(notes, body)])
    document.build(story)
    return buffer.getvalue()
