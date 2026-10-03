from __future__ import annotations

import pytest

from app.services.storefront_refunds import allocate_refund_cents
from f0rge_core.exceptions import ValidationError


def snapshot() -> dict[str, object]:
    return {
        "lines": [
            {"external_line_id": "line-b", "total_minor_zar": 200, "quantity": 1},
            {"external_line_id": "line-a", "total_minor_zar": 100, "quantity": 1},
        ],
        "totals": {"delivery_total_minor_zar": 300, "total_minor_zar": 600},
    }


def test_refund_allocation_uses_largest_remainder_and_preserves_total_cents() -> None:
    # 2 cents over weights 1:2:3 gives raw shares .33, .67, 1.00.
    assert allocate_refund_cents(snapshot(), 2) == {
        "line-a": 0,
        "line-b": 1,
        "delivery": 1,
    }


def test_equal_remainders_break_ties_by_external_line_id_before_delivery() -> None:
    data = {
        "lines": [
            {"external_line_id": "zeta", "total_minor_zar": 1, "quantity": 1},
            {"external_line_id": "alpha", "total_minor_zar": 1, "quantity": 1},
        ],
        "totals": {"delivery_total_minor_zar": 0, "total_minor_zar": 2},
    }
    assert allocate_refund_cents(data, 1) == {"zeta": 0, "alpha": 1}


@pytest.mark.parametrize("amount", [0, -1, 601, True])
def test_refund_allocation_rejects_invalid_or_over_capture_amounts(amount: int) -> None:
    with pytest.raises(ValidationError):
        allocate_refund_cents(snapshot(), amount)


def test_refund_allocation_rejects_snapshot_whose_gross_does_not_match_capture() -> None:
    data = snapshot()
    data["totals"] = {"delivery_total_minor_zar": 300, "total_minor_zar": 700}
    with pytest.raises(ValidationError):
        allocate_refund_cents(data, 50)
