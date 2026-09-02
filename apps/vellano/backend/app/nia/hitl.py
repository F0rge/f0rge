from __future__ import annotations

import json
from typing import Any, Optional

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ToolCallPart

NEEDS_OK_ASSISTANT_TEXT = "Nia needs your approval"
CANCELLED_ASSISTANT_TEXT = "Cancelled."
DEMO_ECHO_TOOL_NAME = "demo_echo_approval"


def dump_agent_messages(messages: list[ModelMessage]) -> list[Any]:
    return json.loads(ModelMessagesTypeAdapter.dump_json(messages))


def load_agent_messages(data: Optional[list[Any]]) -> list[ModelMessage]:
    if not data:
        return []
    return ModelMessagesTypeAdapter.validate_python(data)


def build_needs_ok_payload(approval: ToolCallPart) -> dict[str, Any]:
    args = approval.args if isinstance(approval.args, dict) else {}
    body = str(args.get("text", ""))
    return {
        "kind": "needs_ok",
        "title": "Approve echo",
        "body": body,
        "actions": ["accept", "decline", "cancel"],
        "tool_name": approval.tool_name,
        "tool_call_id": approval.tool_call_id,
    }


def pending_from_deferred(output: DeferredToolRequests) -> Optional[dict[str, Any]]:
    if not output.approvals:
        return None
    return build_needs_ok_payload(output.approvals[0])


def resolve_approval_part(
    output: DeferredToolRequests,
    tool_call_id: Optional[str],
) -> ToolCallPart:
    if tool_call_id:
        for approval in output.approvals:
            if approval.tool_call_id == tool_call_id:
                return approval
    if len(output.approvals) == 1:
        return output.approvals[0]
    raise ValueError("tool_call_id is required when multiple approvals are pending")
