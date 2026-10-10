from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.ops_commerce_order import StorefrontOrderLine

pytestmark = pytest.mark.no_db


def line_payload() -> dict[str, object]:
    return {
        "external_line_id": "line-rounded",
        "source_sku_id": str(UUID(int=1)),
        "sku": "ROUNDED-CHAIR",
        "title": "Rounded chair",
        "quantity": 2,
        "unit_ex_minor_zar": 86956,
        "unit_ex_remainder_minor_zar": 1,
        "ex_minor_zar": 173913,
        "vat_minor_zar": 26087,
        "total_minor_zar": 200000,
    }


def test_allocated_unit_cents_validate_without_changing_line_identity_or_total() -> None:
    line = StorefrontOrderLine.model_validate(line_payload())
    assert line.external_line_id == "line-rounded"
    assert line.model_dump(mode="json")["unit_ex_remainder_minor_zar"] == 1
    assert line.ex_minor_zar + line.vat_minor_zar == line.total_minor_zar


@pytest.mark.parametrize("remainder", [-1, 2, 3])
def test_invalid_unit_cent_allocations_are_rejected(remainder: int) -> None:
    with pytest.raises(ValidationError):
        StorefrontOrderLine.model_validate(
            {**line_payload(), "unit_ex_remainder_minor_zar": remainder}
        )


def test_legacy_exact_unit_payload_keeps_its_canonical_serialized_shape() -> None:
    payload = {
        **line_payload(),
        "unit_ex_minor_zar": 100000,
        "ex_minor_zar": 200000,
        "vat_minor_zar": 30000,
        "total_minor_zar": 230000,
    }
    del payload["unit_ex_remainder_minor_zar"]
    serialized = StorefrontOrderLine.model_validate(payload).model_dump(mode="json")
    assert "unit_ex_remainder_minor_zar" not in serialized
    assert serialized == {**payload, "fulfillment_promise": None}
