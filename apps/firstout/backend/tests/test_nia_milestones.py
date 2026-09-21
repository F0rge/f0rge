"""AG-UI CustomEvent shape for Nia milestones (no_db)."""

from __future__ import annotations

import json

import pytest
from ag_ui.core import CustomEvent, EventType
from ag_ui.encoder import EventEncoder
from pydantic_ai import ToolReturn

from app.nia.agent import NIA_INSTRUCTIONS
from app.nia.milestones import NIA_MILESTONE_EVENT, milestone_event, milestone_tool_return

pytestmark = pytest.mark.no_db


def _payload(encoded: str) -> dict:
    assert encoded.startswith("data:")
    return json.loads(encoded.split("data:", 1)[1].strip())


def test_milestone_custom_event_wire_shape() -> None:
    event = milestone_event("Looking up overdue invoices")
    assert event.type == EventType.CUSTOM
    assert event.name == NIA_MILESTONE_EVENT
    assert event.value == {"label": "Looking up overdue invoices"}

    payload = _payload(EventEncoder().encode(event))
    assert payload["type"] == "CUSTOM"
    assert payload["name"] == NIA_MILESTONE_EVENT
    value = payload["value"]
    assert isinstance(value, dict)
    assert value["label"] == "Looking up overdue invoices"


def test_milestone_tool_return_puts_event_in_metadata() -> None:
    result = milestone_tool_return("  Checking stock  ")
    assert isinstance(result, ToolReturn)
    assert result.return_value == "Noted: Checking stock"
    metadata = result.metadata
    assert isinstance(metadata, CustomEvent)
    assert metadata.name == NIA_MILESTONE_EVENT
    assert metadata.value == {"label": "Checking stock"}


def test_milestone_tool_return_rejects_blank_label() -> None:
    result = milestone_tool_return("   ")
    assert result.return_value == "Milestone label is required"
    assert result.metadata is None


def test_instructions_tell_nia_to_report_milestones() -> None:
    assert "`report_milestone`" in NIA_INSTRUCTIONS
    assert "between steps" in NIA_INSTRUCTIONS
