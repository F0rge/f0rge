from __future__ import annotations

import pytest

from app.nia.fields import canonical_field_values


pytestmark = pytest.mark.no_db


def test_barcode_alias_maps_to_our_barcode() -> None:
    values = canonical_field_values({"name": "Nia Test", "barcode": "9900002026090301"})
    assert values["our_barcode"] == "9900002026090301"
    assert values["name"] == "Nia Test"


def test_existing_our_barcode_is_not_overwritten() -> None:
    values = canonical_field_values({"our_barcode": "keep-me", "barcode": "ignore"})
    assert values["our_barcode"] == "keep-me"
