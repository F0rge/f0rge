"""Prove the AG-UI wire format and Nia SSE response headers."""

from __future__ import annotations

import json

import pytest
from ag_ui.core import ReasoningMessageContentEvent, TextMessageContentEvent, ToolCallStartEvent
from ag_ui.encoder import EventEncoder
from starlette.responses import StreamingResponse

from app.services.nia_sse import NIA_SSE_HEADERS, apply_nia_sse_headers

pytestmark = pytest.mark.no_db


def _payload(encoded: str) -> dict:
    assert encoded.startswith("data:")
    return json.loads(encoded.split("data:", 1)[1].strip())


def test_agui_encode_event_text_delta_shape() -> None:
    """Capture what PydanticAI / ag-ui-protocol actually writes on the wire."""
    encoded = EventEncoder().encode(
        TextMessageContentEvent(message_id="msg_1", delta="Hello"),
    )
    payload = _payload(encoded)
    assert payload["type"] == "TEXT_MESSAGE_CONTENT"
    assert payload["delta"] == "Hello"
    assert payload.get("messageId") == "msg_1" or payload.get("message_id") == "msg_1"


def test_agui_encode_event_tool_start_shape() -> None:
    encoded = EventEncoder().encode(
        ToolCallStartEvent(
            tool_call_id="call_1",
            tool_call_name="create_sku",
        ),
    )
    payload = _payload(encoded)
    assert payload["type"] == "TOOL_CALL_START"
    assert (
        payload.get("toolCallName") == "create_sku" or payload.get("tool_call_name") == "create_sku"
    )


def test_agui_encode_event_reasoning_shape() -> None:
    encoded = EventEncoder().encode(
        ReasoningMessageContentEvent(message_id="think_1", delta="hmm"),
    )
    payload = _payload(encoded)
    assert payload["type"] == "REASONING_MESSAGE_CONTENT"
    assert payload["delta"] == "hmm"


async def test_apply_nia_sse_headers() -> None:
    async def _empty():
        if False:
            yield b""

    response = StreamingResponse(_empty(), media_type="application/octet-stream")
    apply_nia_sse_headers(response)
    for key, value in NIA_SSE_HEADERS.items():
        assert response.headers[key.lower()] == value
