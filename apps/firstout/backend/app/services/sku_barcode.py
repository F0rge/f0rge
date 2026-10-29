"""Barcode assigned when a new SKU is saved with the field left blank.

Matches the catalogue CSV import and the purchase-order placeholder: ``csv:<our_ref>``.
The column stays required and unique; only the create path fills a blank. Existing
rows are not rewritten.
"""

from __future__ import annotations

BARCODE_MAX_LENGTH = 64


def csv_style_barcode(our_ref: str, attempt: int = 1) -> str:
    """Return ``csv:<our_ref>``, or ``csv:<our_ref>-N`` when ``attempt`` is greater than 1.

    Both forms are at most 64 characters, the ``skus.our_barcode`` limit.
    """
    base = f"csv:{our_ref.strip()}"
    if attempt <= 1:
        return base[:BARCODE_MAX_LENGTH]
    suffix = f"-{attempt}"
    keep = BARCODE_MAX_LENGTH - len(suffix)
    return f"{base[:keep]}{suffix}"
