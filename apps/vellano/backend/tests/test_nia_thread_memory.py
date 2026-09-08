"""Nia restores PydanticAI history for follow-ups in the same thread."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic_ai import models
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from starlette.requests import Request
from starlette.responses import Response

from app.nia.agent import NiaDeps, nia_agent
from app.nia.hitl import (
    MAX_HISTORY_USER_TURNS,
    dump_agent_messages,
    load_agent_messages,
)
from app.services.nia_run import NiaRunService

models.ALLOW_MODEL_REQUESTS = False
pytestmark = pytest.mark.no_db


def _text(messages: list[ModelMessage]) -> str:
    values: list[str] = []
    for message in messages:
        for part in message.parts:
            content = getattr(part, "content", None)
            if isinstance(content, str):
                values.append(content)
    return "\n".join(values)


def _request(payload: dict[str, Any]) -> Request:
    body = json.dumps(payload).encode()
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/"}, receive)


async def test_serialized_history_round_trips_and_keeps_recent_turns() -> None:
    messages: list[ModelMessage] = []
    for turn in range(MAX_HISTORY_USER_TURNS + 2):
        messages.extend(
            [
                ModelRequest(parts=[UserPromptPart(content=f"question-{turn}")]),
                ModelResponse(parts=[TextPart(content=f"answer-{turn}")]),
            ]
        )

    restored = load_agent_messages(dump_agent_messages(messages))

    assert len(restored) == MAX_HISTORY_USER_TURNS * 2
    contents = _text(restored).splitlines()
    assert "question-0" not in contents
    assert "question-1" not in contents
    assert "question-2" in contents
    assert f"answer-{MAX_HISTORY_USER_TURNS + 1}" in contents


async def test_function_model_follow_up_receives_first_turn_history() -> None:
    deps = NiaDeps(
        user_id=uuid.uuid4(),
        permissions=[],
        page_path="/canvas",
        db=None,
    )
    first = await nia_agent.run(
        "The chart contains Dining and Sofas, with one SKU.",
        deps=deps,
        model=FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[TextPart(content="I charted Dining versus Sofas; there is one SKU.")]
            )
        ),
    )
    stored = dump_agent_messages(first.all_messages())
    seen: list[ModelMessage] = []

    def answer_follow_up(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.extend(messages)
        context = _text(messages)
        if "one SKU" in context and "Dining versus Sofas" in context:
            answer = "Yes — the chart has one SKU across Dining and Sofas."
        else:
            answer = "I do not have earlier context."
        return ModelResponse(parts=[TextPart(content=answer)])

    second = await nia_agent.run(
        "But there's only 1 SKU there?",
        deps=deps,
        model=FunctionModel(answer_follow_up),
        message_history=load_agent_messages(stored),
    )

    assert "one SKU across Dining and Sofas" in second.output
    assert "I charted Dining versus Sofas" in _text(seen)
    assert "But there's only 1 SKU there?" in _text(seen)


async def test_dispatch_run_passes_db_history_to_agui_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = [
        ModelRequest(parts=[UserPromptPart(content="Chart dining versus sofas")]),
        ModelResponse(parts=[TextPart(content="The chart contains one SKU.")]),
    ]
    thread = SimpleNamespace(agent_messages=dump_agent_messages(prior), messages=[])

    class FakeThreads:
        async def get_owned_thread(self, user_id: uuid.UUID, thread_id: uuid.UUID) -> Any:
            return thread

    class FakePermissions:
        async def keys_for_user(self, user_id: uuid.UUID) -> list[str]:
            return []

    captured: dict[str, Any] = {}

    class FakeAdapter:
        def __init__(self, agent: Any, run_input: Any) -> None:
            captured["run_input"] = run_input

        def run_stream(self, **kwargs: Any) -> object:
            captured["kwargs"] = kwargs
            return object()

        def streaming_response(self, stream: object) -> Response:
            return Response()

    async def allow_budget(db: Any, user_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr("app.services.nia_run.AGUIAdapter", FakeAdapter)
    monkeypatch.setattr("app.services.nia_run.build_nia_model", lambda: object())
    monkeypatch.setattr("app.services.nia_run.check_nia_budget", allow_budget)
    monkeypatch.setattr("app.services.nia_run.settings.openrouter_api_key", "test-key")

    service = NiaRunService(None)
    service.threads = FakeThreads()  # type: ignore[assignment]
    service.permissions = FakePermissions()  # type: ignore[assignment]
    await service.dispatch_run(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        request=_request({"message": "But there's only 1 SKU there?"}),
    )

    history = captured["kwargs"]["message_history"]
    assert "Chart dining versus sofas" in _text(history)
    assert "The chart contains one SKU." in _text(history)
