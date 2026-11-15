from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from pydantic import TypeAdapter, ValidationError as PydanticValidationError

from app.schemas.quantity import Quantity
from f0rge_core.exceptions import ValidationError

_quantity = TypeAdapter(Quantity)


def exact_quantity(value: object) -> Decimal:
    """Validate service/import callers as strictly as API inputs, without rounding."""
    try:
        return _quantity.validate_python(value)
    except PydanticValidationError as exc:
        raise ValidationError(
            "Quantity must be finite with at most 4 decimal places and 10 integer digits"
        ) from exc


def whole_available_quantity(value: Decimal) -> int:
    """Whole-item capacity at a boundary; never write this projection back to stock."""
    return int(max(Decimal(0), Decimal(value)).to_integral_value(rounding=ROUND_FLOOR))
