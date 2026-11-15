from __future__ import annotations

from app.models.sku import Sku
from f0rge_core.exceptions import ValidationError


def assert_sku_sellable(sku: Sku) -> None:
    """Check new sales only; stock and existing commitments retain their SKU."""
    if sku.is_sellable is False:
        raise ValidationError(f"SKU {sku.our_ref} is not available for new sales")
