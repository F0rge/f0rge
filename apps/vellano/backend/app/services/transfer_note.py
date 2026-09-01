from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _fmt_ts(value: Optional[datetime]) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M")


def build_transfer_note_pdf(
    transfer_number: str,
    status: str,
    from_location_name: str,
    to_location_name: str,
    dispatcher_name: Optional[str],
    dispatched_at: Optional[datetime],
    receiver_name: Optional[str],
    received_at: Optional[datetime],
    lines: list[tuple[str, str, int, Optional[int]]],
) -> bytes:
    """Build an in-app Transfer Note. Each line: our_ref, name, qty_dispatched, qty_received."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    height = A4[1]
    y = height - 30 * mm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30 * mm, y, f"Transfer Note — {transfer_number}")
    y -= 10 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(30 * mm, y, f"Status: {status}")
    y -= 6 * mm
    pdf.drawString(30 * mm, y, f"From: {from_location_name}")
    y -= 6 * mm
    pdf.drawString(30 * mm, y, f"To: {to_location_name}")
    y -= 6 * mm
    dispatcher = dispatcher_name or "—"
    pdf.drawString(30 * mm, y, f"Dispatched by: {dispatcher} at {_fmt_ts(dispatched_at)}")
    y -= 6 * mm
    if receiver_name is not None or received_at is not None:
        receiver = receiver_name or "—"
        pdf.drawString(30 * mm, y, f"Received by: {receiver} at {_fmt_ts(received_at)}")
        y -= 6 * mm
    y -= 4 * mm

    for our_ref, name, qty_dispatched, qty_received in lines:
        if y < 40 * mm:
            pdf.showPage()
            y = height - 30 * mm
            pdf.setFont("Helvetica", 10)

        pdf.drawString(30 * mm, y, f"Ref: {our_ref}")
        y -= 6 * mm
        pdf.drawString(30 * mm, y, f"Name: {name}")
        y -= 6 * mm
        pdf.drawString(30 * mm, y, f"Qty dispatched: {qty_dispatched}")
        y -= 6 * mm
        if qty_received is not None:
            pdf.drawString(30 * mm, y, f"Qty received: {qty_received}")
            y -= 6 * mm
        y -= 4 * mm

    pdf.save()
    return buffer.getvalue()
