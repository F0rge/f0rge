from __future__ import annotations

from app.services.placeholder_pdf import PLACEHOLDER_PDF, is_openable_pdf

MINIMAL_PDF = PLACEHOLDER_PDF


def assert_pdf_openable(content: bytes) -> None:
    assert is_openable_pdf(content), "PDF missing %PDF header or startxref"
