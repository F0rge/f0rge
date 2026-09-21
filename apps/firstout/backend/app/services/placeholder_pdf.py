from __future__ import annotations

from io import BytesIO

from reportlab.pdfgen import canvas


def build_placeholder_pdf(title: str = "Playground placeholder") -> bytes:
    buf = BytesIO()
    page = canvas.Canvas(buf)
    page.drawString(72, 800, title)
    page.save()
    return buf.getvalue()


def is_openable_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF") and b"startxref" in data


PLACEHOLDER_PDF = build_placeholder_pdf()
