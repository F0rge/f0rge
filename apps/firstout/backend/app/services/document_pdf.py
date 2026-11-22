"""One ReportLab layout for every customer document, driven by the team's template.

Tax invoices, quotes, credit notes and payment receipts all print through
``render_document_pdf``: title and dates, logo, Seller | Buyer, a line table with a
header band, right-aligned totals, then the template's other sections in its order.
Services build a ``DocumentData`` from their own records; only printed text goes in it,
so an internal note can never reach the page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    LongTable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.document_template import DocumentKind, DocumentTemplate
from app.services.invoice_pdf import SellerDetails
from app.services.vat import vat_percent

FONTS = {
    "sans": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"),
    "serif": ("Times-Roman", "Times-Bold", "Times-Italic"),
    "mono": ("Courier", "Courier-Bold", "Courier-Oblique"),
}
MUTED = colors.HexColor("#525252")
RULE = colors.HexColor("#e0e0e0")
STAMP_COLOURS = {"Paid": "#198038", "On statement": "#0f62fe", "Void": "#da1e28"}
MARGIN = 18 * mm
FOOTER_SPACE = 18 * mm


@dataclass(frozen=True)
class DocumentParty:
    label: str
    name: str
    address: Optional[str] = None
    vat_number: Optional[str] = None


@dataclass(frozen=True)
class DocumentLine:
    description: str
    qty: str
    unit: str
    ex_vat: str
    vat: str
    inc_vat: str
    discount: Optional[str] = None
    sku_ref: Optional[str] = None


@dataclass
class DocumentData:
    kind: DocumentKind
    number: str
    issue_date: str
    party: DocumentParty
    total: str
    subtotal_ex_vat: Optional[str] = None
    vat_amount: Optional[str] = None
    # The document's stored VAT rate (ADR 0003); a receipt has none.
    vat_rate: Optional[Decimal] = None
    total_label: str = "Total"
    lines: list[DocumentLine] = field(default_factory=list)
    # A receipt has no VAT lines: (description, amount) rows instead.
    amount_rows: list[tuple[str, str]] = field(default_factory=list)
    details: list[tuple[str, str]] = field(default_factory=list)
    served_by: Optional[str] = None
    payments: list[tuple[str, str]] = field(default_factory=list)
    note: Optional[str] = None
    unit_basis_note: Optional[str] = None
    unit_header: str = "Unit excl. VAT"
    # "paid" / "on_statement" follow the template's paid_stamp; "void" always prints.
    status: Optional[str] = None
    payment_reference: bool = False


def _text(value: str) -> str:
    # User text is always literal; only the newline tag below is markup.
    return escape(value).replace("\n", "<br/>")


def _stamp(data: DocumentData, template: DocumentTemplate) -> Optional[str]:
    if data.status == "void":
        return "Void"
    if not template.paid_stamp:
        return None
    return {"paid": "Paid", "on_statement": "On statement"}.get(data.status or "")


def _logo(seller: SellerDetails, template: DocumentTemplate) -> Optional[Image]:
    if not seller.logo_bytes:
        return None
    try:
        width, height = ImageReader(BytesIO(seller.logo_bytes)).getSize()
    except Exception:
        return None
    # The template's height is in screen pixels on a ~820 px wide page preview.
    draw_h = template.logo_height * 0.72
    draw_w = min(draw_h * width / height, draw_h * 2.5)
    return Image(BytesIO(seller.logo_bytes), width=draw_w, height=draw_w * height / width)


def render_document_pdf(
    data: DocumentData, template: DocumentTemplate, seller: SellerDetails
) -> bytes:
    regular, bold, italic = FONTS[template.font]
    compact = template.density == "compact"
    size = 8 if compact else 9
    pad = 3 if compact else 5
    accent = colors.HexColor(template.accent_colour)
    wording = getattr(template.wording, data.kind)
    vat_label = (
        f"{vat_percent(data.vat_rate)}%".replace(".00%", "%") if data.vat_rate is not None else ""
    )
    width, height = A4
    body_width = width - 2 * MARGIN

    body = ParagraphStyle("doc-body", fontName=regular, fontSize=size, leading=size * 1.4)
    strong = ParagraphStyle("doc-strong", parent=body, fontName=bold)
    right = ParagraphStyle("doc-right", parent=body, alignment=2)
    right_strong = ParagraphStyle("doc-right-strong", parent=right, fontName=bold)
    muted = ParagraphStyle("doc-muted", parent=body, textColor=MUTED, fontSize=size - 1)
    heading = ParagraphStyle(
        "doc-heading", parent=strong, textColor=MUTED, spaceBefore=5 * mm, keepWithNext=True
    )
    align = 1 if template.logo_position == "centre" else 0
    brand_align = {"left": 0, "centre": 1, "right": 2}[template.logo_position]
    head_style = ParagraphStyle("doc-head", parent=body, alignment=align)
    title = ParagraphStyle(
        "doc-title",
        parent=head_style,
        fontSize=20,
        leading=26,
        textColor=accent,
        spaceAfter=2 * mm,
    )

    def para(value: str, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(_text(value), style)

    def labelled(label: str, value: str) -> Paragraph:
        return Paragraph(f'<font color="#525252">{_text(label)}</font> {_text(value)}', head_style)

    def right_table(rows: list[tuple[str, str]], grand: bool) -> Table:
        cells = [[para(label, right), para(value, right)] for label, value in rows]
        if grand:
            cells[-1] = [para(rows[-1][0], right_strong), para(rows[-1][1], right_strong)]
        table = Table(cells, colWidths=[55 * mm, 32 * mm], hAlign="RIGHT")
        style = [("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
        if grand:
            style.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black))
        table.setStyle(TableStyle(style))
        return table

    # --- header: title block beside (or under) the logo -------------------------
    head = [para(wording.title, title), labelled(wording.number_label, data.number)]
    head.append(labelled("Issue date", data.issue_date))
    head.extend(labelled(label, value) for label, value in data.details)
    if data.served_by:
        head.append(labelled("Served by", data.served_by))
    stamp = _stamp(data, template)
    if stamp:
        stamp_colour = colors.HexColor(STAMP_COLOURS[stamp])
        stamp_style = ParagraphStyle(
            "doc-stamp", parent=strong, textColor=stamp_colour, fontSize=size + 2
        )
        badge = Table(
            [[Paragraph(stamp.upper(), stamp_style)]],
            colWidths=[stringWidth(stamp.upper(), bold, size + 2) + 14],
            hAlign="CENTER" if align else "LEFT",
        )
        badge.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.5, stamp_colour)]))
        head.extend([Spacer(1, 2 * mm), badge])
    brand: list = []
    logo = _logo(seller, template)
    if logo is not None:
        logo.hAlign = ("LEFT", "CENTER", "RIGHT")[brand_align]
        brand.append(logo)
    if template.show_trading_name and seller.trading_name:
        brand_style = ParagraphStyle("doc-brand", parent=strong, alignment=brand_align)
        brand.append(para(seller.trading_name, brand_style))
    if template.logo_position == "centre":
        header = Table([[brand or ""], [head]], colWidths=[body_width])
        brand_cell = (0, 0)
    elif template.logo_position == "left":
        header = Table([[brand or "", head]], colWidths=[body_width * 0.4, body_width * 0.6])
        brand_cell = (0, 0)
    else:
        header = Table([[head, brand or ""]], colWidths=[body_width * 0.6, body_width * 0.4])
        brand_cell = (1, 0)
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("ALIGN", brand_cell, brand_cell, ("LEFT", "CENTER", "RIGHT")[brand_align]),
            ]
        )
    )
    story: list = [header]

    # --- sections, in the template's order ---------------------------------------
    def parties() -> list:
        seller_name = seller.name
        if template.show_trading_name and seller.trading_name:
            seller_name = f"{seller.name} t/a {seller.trading_name}"
        left = [para("Seller", muted), para(seller_name, strong)]
        left += [para(seller.address), para(f"VAT {seller.vat_number}")]
        party = data.party
        right_col = [para(party.label, muted), para(party.name or "-", strong)]
        if party.address:
            right_col.append(para(party.address))
        if party.vat_number:
            right_col.append(para(f"VAT {party.vat_number}"))
        table = Table([[left, right_col]], colWidths=[body_width / 2, body_width / 2])
        table.setStyle(
            TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])
        )
        return [Spacer(1, 7 * mm), table]

    def line_table() -> list:
        header_text = ParagraphStyle("doc-th", parent=strong, fontSize=size)
        header_right = ParagraphStyle("doc-th-right", parent=header_text, alignment=2)
        if template.table_header == "solid":
            header_text.textColor = header_right.textColor = colors.white
        if data.amount_rows:
            columns = [("Description", None), ("Amount", 40 * mm)]
            rows = [[para(desc), para(amount, right)] for desc, amount in data.amount_rows]
        else:
            show_discount = template.columns.discount and any(ln.discount for ln in data.lines)
            columns = [("Description", None), ("Qty", 12 * mm), (data.unit_header, 30 * mm)]
            if show_discount:
                columns.append(("Disc.", 14 * mm))
            columns.append(("Excl. VAT", 24 * mm))
            if template.columns.line_vat:
                columns.append((f"VAT {vat_label}", 22 * mm))
            columns.append(("Incl. VAT", 24 * mm))
            rows = []
            for line in data.lines:
                description = line.description
                if line.discount and not show_discount:
                    description = f"{description} ({line.discount} discount)"
                cell = [para(description)]
                if template.columns.sku_ref and line.sku_ref:
                    cell.append(para(line.sku_ref, muted))
                row = [cell, para(line.qty, right), para(line.unit, right)]
                if show_discount:
                    row.append(para(line.discount or "", right))
                row.append(para(line.ex_vat, right))
                if template.columns.line_vat:
                    row.append(para(line.vat, right))
                row.append(para(line.inc_vat, right))
                rows.append(row)
        fixed = sum(w for _, w in columns if w)
        widths = [w or body_width - fixed for _, w in columns]
        head_row = [
            Paragraph(_text(name), header_text if i == 0 else header_right)
            for i, (name, _) in enumerate(columns)
        ]
        table = LongTable([head_row, *rows], colWidths=widths, repeatRows=1)
        style = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), pad),
            ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, RULE),
        ]
        if template.table_header == "band":
            # A light tint of the accent; the default black accent gets the grey band.
            band = RULE
            if template.accent_colour != "#161616":
                band = colors.Color(*(1 - 0.15 * (1 - c) for c in accent.rgb()))
            style.append(("BACKGROUND", (0, 0), (-1, 0), band))
        elif template.table_header == "solid":
            style.append(("BACKGROUND", (0, 0), (-1, 0), accent))
        else:
            style.append(("LINEBELOW", (0, 0), (-1, 0), 1.2, accent))
        table.setStyle(TableStyle(style))
        out: list = [Spacer(1, 7 * mm)]
        if data.unit_basis_note and not data.amount_rows:
            basis = ParagraphStyle("doc-basis", parent=muted, fontName=italic)
            out += [para(data.unit_basis_note, basis), Spacer(1, 1.5 * mm)]
        return [*out, table]

    def totals() -> list:
        rows = []
        if data.subtotal_ex_vat is not None:
            rows.append(("Subtotal excl. VAT", data.subtotal_ex_vat))
        if data.vat_amount is not None:
            rows.append((f"VAT ({vat_label})", data.vat_amount))
        rows.append((data.total_label, data.total))
        return [Spacer(1, 4 * mm), right_table(rows, grand=True)]

    def block(name: str, *paragraphs: str) -> list:
        return [para(name, heading), *(para(text) for text in paragraphs)]

    def bank() -> list:
        if not (seller.bank_name and seller.bank_account):
            return []
        detail = f"{seller.bank_name} · Account {seller.bank_account}"
        if seller.bank_branch_code:
            detail += f" · Branch {seller.bank_branch_code}"
        lines = [detail]
        if data.payment_reference:
            lines.append(f"Use {data.number} as your payment reference.")
        return block("Banking details", *lines)

    sections = {
        "parties": parties,
        "lines": line_table,
        "totals": totals,
        "notes": lambda: block("Note", data.note) if data.note else [],
        "payments": lambda: (
            [Spacer(1, 2 * mm), right_table(data.payments, grand=True)] if data.payments else []
        ),
        "bank": bank,
        "terms": lambda: block("Terms", wording.terms) if wording.terms.strip() else [],
    }
    for section in template.sections:
        if section.visible:
            story.extend(sections[section.key]())

    footer_lines = [
        line
        for paragraph in template.footer.splitlines()
        for line in simpleSplit(paragraph, regular, 8, body_width - 25 * mm)
    ][:3]

    def page_footer(pdf, doc) -> None:
        pdf.saveState()
        pdf.setStrokeColor(RULE)
        pdf.line(MARGIN, FOOTER_SPACE - 2 * mm, width - MARGIN, FOOTER_SPACE - 2 * mm)
        pdf.setFillColor(MUTED)
        pdf.setFont(regular, 8)
        y = FOOTER_SPACE - 6 * mm
        for line in footer_lines:
            pdf.drawString(MARGIN, y, line)
            y -= 3.5 * mm
        pdf.drawRightString(width - MARGIN, FOOTER_SPACE - 6 * mm, f"Page {doc.page}")
        pdf.restoreState()

    buffer = BytesIO()
    document = BaseDocTemplate(
        buffer, pagesize=A4, title=f"{wording.title} {data.number}", author=seller.name
    )
    top = MARGIN - (4 * mm if compact else 0)
    frame = Frame(
        MARGIN,
        FOOTER_SPACE,
        body_width,
        height - top - FOOTER_SPACE,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates(PageTemplate(id="document", frames=[frame], onPage=page_footer))
    document.build(story)
    return buffer.getvalue()


def sample_document(kind: DocumentKind) -> DocumentData:
    """Example content so a team with no documents yet still sees its template."""
    party = DocumentParty(
        label="Prepared for" if kind == "quote" else "Buyer",
        name="Sample Customer (Pty) Ltd",
        address="1 Example Road, Johannesburg",
        vat_number="4000000000",
    )
    if kind == "receipt":
        return DocumentData(
            kind=kind,
            number="PAY-0001",
            issue_date="2026-01-15",
            party=DocumentParty(label="Received from", name=party.name, address=party.address),
            details=[("Method", "EFT"), ("Reference", "INV-0001"), ("Against", "Invoice INV-0001")],
            amount_rows=[("Payment against invoice INV-0001", "11500.00 ZAR")],
            total="11500.00 ZAR",
            total_label="Amount received",
            payments=[
                ("Invoice total", "11500.00"),
                ("Paid to date", "11500.00"),
                ("Balance owing", "0.00"),
            ],
            status="paid",
        )
    lines = [
        DocumentLine(
            "Three-seater sofa", "1", "8000.00", "8000.00", "1200.00", "9200.00", None, "SOFA-001"
        ),
        DocumentLine(
            "Side table", "2", "1052.63", "2000.00", "300.00", "2300.00", "5.00%", "TBL-002"
        ),
    ]
    details: list[tuple[str, str]] = []
    number = {"invoice": "INV-0001", "quote": "QUO-0001", "credit_note": "CN-0001"}[kind]
    if kind == "invoice":
        details.append(("Due date", "2026-02-14"))
    elif kind == "quote":
        details.append(("Valid until", "2026-01-29"))
    else:
        details += [("Against invoice", "INV-0001"), ("Reason", "Returned in good condition")]
    return DocumentData(
        kind=kind,
        number=number,
        issue_date="2026-01-15",
        party=party,
        lines=lines,
        details=details,
        served_by="Sam",
        subtotal_ex_vat="10000.00",
        vat_amount="1500.00",
        # The sample amounts above are worked at 15%; a sample, not a rate rule.
        vat_rate=Decimal("0.15"),
        total="11500.00",
        payments=[("Paid", "5000.00"), ("Balance owing", "6500.00")] if kind == "invoice" else [],
        note="This is a sample printed note. Delivery within 10 working days."
        if kind != "credit_note"
        else None,
        unit_basis_note="Unit prices excl. VAT. VAT is added to the total.",
        status="on_statement" if kind == "invoice" else None,
        payment_reference=kind in ("invoice", "quote"),
    )
