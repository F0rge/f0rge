"""ZA mobile E.164 for WhatsApp."""

from __future__ import annotations

from typing import Optional

import pytest

from app.services.comms.phone import to_whatsapp_e164

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0824112001", "+27824112001"),
        ("821234567", "+27821234567"),
        ("+27821234567", "+27821234567"),
        ("0027821234567", "+27821234567"),
        ("082 411 2001", "+27824112001"),
        ("0118802101", None),
        ("+27118802101", None),
        ("0800123456", None),
        ("+919876543210", None),
        ("", None),
        (None, None),
    ],
)
def test_to_whatsapp_e164(raw: Optional[str], expected: Optional[str]) -> None:
    assert to_whatsapp_e164(raw) == expected
