from __future__ import annotations

from io import BytesIO
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_pick_sheet_pdf(
    pick_number: str,
    customer_name: Optional[str],
    kit_label: str,
    sections: list[tuple[str, list[tuple[str, str, int]]]],
    completeness: list[tuple[str, int, int]],
) -> bytes:
    """Pick sheet. sections: (location_name, [(our_ref, name, qty)]). completeness: (name, allocated, needed)."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    height = A4[1]
    y = height - 30 * mm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30 * mm, y, f"Pick — {pick_number}")
    y -= 10 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(30 * mm, y, f"Customer: {customer_name or '—'}")
    y -= 6 * mm
    pdf.drawString(30 * mm, y, f"Kit: {kit_label}")
    y -= 10 * mm

    for location_name, lines in sections:
        if y < 40 * mm:
            pdf.showPage()
            y = height - 30 * mm
            pdf.setFont("Helvetica", 10)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(30 * mm, y, location_name)
        y -= 6 * mm
        pdf.setFont("Helvetica", 10)
        for our_ref, name, qty in lines:
            if y < 40 * mm:
                pdf.showPage()
                y = height - 30 * mm
                pdf.setFont("Helvetica", 10)
            pdf.drawString(30 * mm, y, f"{our_ref}  {name}  × {qty}")
            y -= 6 * mm
        y -= 4 * mm

    if y < 50 * mm:
        pdf.showPage()
        y = height - 30 * mm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(30 * mm, y, "Set completeness")
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    for name, allocated, needed in completeness:
        if y < 30 * mm:
            pdf.showPage()
            y = height - 30 * mm
            pdf.setFont("Helvetica", 10)
        pdf.drawString(30 * mm, y, f"{name} {allocated}/{needed}")
        y -= 6 * mm

    pdf.save()
    return buffer.getvalue()
