"""AG-UI custom events for Nia mid-run progress."""

from __future__ import annotations

from typing import Any, Optional

from ag_ui.core import CustomEvent, EventType
from pydantic_ai import ToolReturn

NIA_MILESTONE_EVENT = "nia.milestone"


def milestone_event(label: str, progress: Optional[float] = None) -> CustomEvent:
    """Build the AG-UI CustomEvent the frontend maps to a live progress line."""
    value: dict[str, Any] = {"label": label}
    if progress is not None:
        value["progress"] = progress
    return CustomEvent(
        type=EventType.CUSTOM,
        name=NIA_MILESTONE_EVENT,
        value=value,
    )


def milestone_tool_return(label: str) -> ToolReturn:
    """ToolReturn whose metadata is yielded onto the AG-UI SSE stream."""
    text = label.strip()
    if not text:
        return ToolReturn(return_value="Milestone label is required")
    return ToolReturn(
        return_value=f"Noted: {text}",
        metadata=milestone_event(text),
    )
