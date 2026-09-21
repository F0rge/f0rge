from __future__ import annotations

import csv
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.schemas.bank_import import Vat201Draft


def build_vat201_csv(draft: Vat201Draft) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["VAT201 Draft — manual eFiling entry only"])
    writer.writerow(["Period from", draft.period_from.isoformat()])
    writer.writerow(["Period to", draft.period_to.isoformat()])
    writer.writerow(["Vendor", draft.vendor_name])
    writer.writerow(["VAT number", draft.vendor_vat_number])
    writer.writerow([])
    writer.writerow(["Field", "Description", "Amount (ZAR)"])
    writer.writerow(
        ["1", "Standard rated supplies (excl VAT)", f"{draft.standard_rated_supplies_ex_vat:.2f}"]
    )
    writer.writerow(["2", "Output tax at 15%", f"{draft.output_tax:.2f}"])
    writer.writerow(["3", "Input tax", f"{draft.input_tax:.2f}"])
    writer.writerow(["4", "Net VAT payable", f"{draft.net_vat_payable:.2f}"])
    writer.writerow([])
    writer.writerow(["Invoices in period", draft.invoice_count])
    writer.writerow(["Credit notes in period", draft.credit_note_count])
    writer.writerow([])
    writer.writerow([draft.disclaimer])
    return buffer.getvalue().encode("utf-8")


def build_vat201_pdf(draft: Vat201Draft) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(25 * mm, y, "VAT201 Draft")
    y -= 8 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(25 * mm, y, "For manual entry into SARS eFiling — not filed by this application")
    y -= 12 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, y, f"Period: {draft.period_from} to {draft.period_to}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Vendor: {draft.vendor_name}  VAT: {draft.vendor_vat_number}")
    y -= 12 * mm

    rows = [
        ("1", "Standard rated supplies (excl VAT)", draft.standard_rated_supplies_ex_vat),
        ("2", "Output tax at 15%", draft.output_tax),
        ("3", "Input tax", draft.input_tax),
        ("4", "Net VAT payable", draft.net_vat_payable),
    ]
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(25 * mm, y, "Field")
    pdf.drawString(40 * mm, y, "Description")
    pdf.drawRightString(width - 25 * mm, y, "Amount (ZAR)")
    y -= 8 * mm
    pdf.setFont("Helvetica", 10)
    for field, label, amount in rows:
        pdf.drawString(25 * mm, y, field)
        pdf.drawString(40 * mm, y, label)
        pdf.drawRightString(width - 25 * mm, y, f"{amount:.2f}")
        y -= 6 * mm

    y -= 8 * mm
    pdf.drawString(
        25 * mm, y, f"Invoices: {draft.invoice_count}  Credit notes: {draft.credit_note_count}"
    )
    y -= 12 * mm
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(25 * mm, y, draft.disclaimer)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
