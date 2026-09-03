from __future__ import annotations

import json
from typing import Any, Optional

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ToolCallPart,
    UserPromptPart,
)

NEEDS_OK_ASSISTANT_TEXT = "Nia needs your approval"
CANCELLED_ASSISTANT_TEXT = "Cancelled."
DEMO_ECHO_TOOL_NAME = "demo_echo_approval"
MAX_HISTORY_USER_TURNS = 20


def limit_agent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Keep complete message groups for the most recent user turns."""
    user_turn_starts = [
        index
        for index, message in enumerate(messages)
        if isinstance(message, ModelRequest)
        and any(isinstance(part, UserPromptPart) for part in message.parts)
    ]
    if len(user_turn_starts) <= MAX_HISTORY_USER_TURNS:
        return messages
    return messages[user_turn_starts[-MAX_HISTORY_USER_TURNS] :]


def dump_agent_messages(messages: list[ModelMessage]) -> list[Any]:
    bounded = limit_agent_messages(messages)
    return json.loads(ModelMessagesTypeAdapter.dump_json(bounded))


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
    approval = output.approvals[0]
    meta = output.metadata.get(approval.tool_call_id or "")
    if isinstance(meta, dict) and meta.get("kind"):
        payload = dict(meta)
        payload.setdefault("tool_name", approval.tool_name)
        payload.setdefault("tool_call_id", approval.tool_call_id)
        payload.setdefault("actions", ["accept", "decline", "cancel"])
        return payload
    return build_needs_ok_payload(approval)


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
