from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from app.nia.catalog import CATALOG_BY_ID
from app.nia.fields import (
    NEEDS_FIELDS_KIND,
    build_needs_fields_payload,
    fields_from_model,
    should_emit_fields_form,
)
from app.schemas.sku import SkuCreate


def test_create_sku_fields_include_required() -> None:
    try:
        SkuCreate.model_validate({})
    except PydanticValidationError as exc:
        rows = fields_from_model(SkuCreate, {}, exc)
    else:
        raise AssertionError("expected validation error")
    by_id = {row["id"]: row for row in rows}
    for field_id in ("our_ref", "our_barcode", "name", "design", "fabric"):
        assert by_id[field_id]["required"] is True
        assert by_id[field_id]["type"] == "text"
        assert by_id[field_id]["label"]
    assert "opening_qty" not in by_id


def test_needs_fields_payload_for_create_sku() -> None:
    action = CATALOG_BY_ID["create_sku"]
    assert should_emit_fields_form(action) is True
    try:
        action.args_model.model_validate({})
    except PydanticValidationError as exc:
        payload = build_needs_fields_payload(action, {}, exc)
    else:
        raise AssertionError("expected validation error")
    assert payload["kind"] == NEEDS_FIELDS_KIND
    assert payload["action_id"] == "create_sku"
    assert payload["source"] == "fields"


def test_list_overdue_stays_chat() -> None:
    # Special 0-arg reads are not catalog writes.
    action = CATALOG_BY_ID["list_skus"]
    assert should_emit_fields_form(action) is False
