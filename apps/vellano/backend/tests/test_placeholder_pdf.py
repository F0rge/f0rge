from __future__ import annotations

import pytest

from app.services.placeholder_pdf import PLACEHOLDER_PDF, is_openable_pdf
from tests.pdf_fixture import assert_pdf_openable


@pytest.mark.no_db
def test_placeholder_pdf_is_openable() -> None:
    assert_pdf_openable(PLACEHOLDER_PDF)


@pytest.mark.no_db
def test_stub_bytes_are_not_openable() -> None:
    stub = b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    assert not is_openable_pdf(stub)
