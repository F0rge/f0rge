"""Chart specs survive a later needs_fields / needs_ok turn (Q5 #611)."""

from __future__ import annotations

import pytest

from app.nia.canvas import (
    canvas_payload_to_persist,
    canvas_cleared_payload,
    empty_canvas_spec,
    spec_from_thread_payloads,
)

pytestmark = pytest.mark.no_db


def _dining_spec() -> dict:
    return {
        "kind": "canvas_spec",
        "path": "/canvas",
        "title": "Dining vs sofas this month",
        "components": [
            {
                "type": "bar",
                "id": "dining-vs-sofas",
                "title": "Sales this month (ZAR inc VAT)",
                "categories": ["Dining", "Sofas"],
                "series": [{"name": "Sales", "values": [13800.0, 8050.0]}],
            }
        ],
    }


def _needs_fields_payload() -> dict:
    return {
        "kind": "needs_fields",
        "action_id": "create_sku",
        "title": "Create SKU",
        "fields": [{"id": "our_ref", "label": "Our ref", "type": "text", "required": True}],
        "values": {},
    }


def _needs_ok_payload() -> dict:
    return {
        "kind": "needs_ok",
        "title": "Create SKU",
        "body": "our_ref: QA-20260902-2304",
        "tool_call_id": "call_1",
        "tool_name": "run_nia_action",
        "actions": ["accept", "decline", "cancel"],
    }


def test_chart_then_sku_form_keeps_the_chart() -> None:
    """The SKU form takes the payload slot; the chart is persisted beside it."""
    assert canvas_payload_to_persist(_needs_fields_payload(), _dining_spec()) == _dining_spec()


def test_chart_then_approval_keeps_the_chart() -> None:
    assert canvas_payload_to_persist(_needs_ok_payload(), _dining_spec()) == _dining_spec()


def test_chart_only_turn_is_not_duplicated() -> None:
    spec = _dining_spec()
    assert canvas_payload_to_persist(spec, spec) is None


def test_clear_canvas_turn_is_not_duplicated() -> None:
    cleared = canvas_cleared_payload()
    assert canvas_payload_to_persist(cleared, cleared) is None


def test_clear_survives_a_later_write_payload() -> None:
    cleared = canvas_cleared_payload()
    assert canvas_payload_to_persist(_needs_ok_payload(), cleared) == cleared


def test_no_canvas_tool_in_the_turn_persists_nothing() -> None:
    assert canvas_payload_to_persist(_needs_fields_payload(), None) is None
    assert canvas_payload_to_persist(None, None) is None
    assert canvas_payload_to_persist(_needs_fields_payload(), {"kind": "opened_page"}) is None


def test_thread_history_rebuild_ignores_needs_fields() -> None:
    """A needs_fields payload after a chart must not reset the canvas."""
    rebuilt = spec_from_thread_payloads(
        [_dining_spec(), _needs_fields_payload(), _needs_ok_payload()]
    )
    assert rebuilt["title"] == "Dining vs sofas this month"
    assert [item["id"] for item in rebuilt["components"]] == ["dining-vs-sofas"]

    wiped = spec_from_thread_payloads([_dining_spec(), canvas_cleared_payload()])
    assert wiped == empty_canvas_spec()
