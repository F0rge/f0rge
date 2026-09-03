"""One chained turn keeps the chart on the thread (Q5 #611).

`chart dining vs sofas this month, then help me add a new colour SKU` runs a
chart tool and a write tool in the SAME agent run. The turn has one
structured-payload slot and the write tool claims it, so the chart has to be
persisted as its own message or `/canvas` reads an empty canvas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import app.nia  # noqa: F401 — register Nia tools on the agent
from app.nia.agent import NiaDeps, nia_agent
from app.nia.canvas import CANVAS_PATH, CANVAS_SPEC_KIND, spec_from_thread_payloads
from app.nia.hitl import richer_needs_ok
from app.permissions import CATALOGUE_MUTATE, NIA_USE
from app.services.nia_run import NiaRunService

models.ALLOW_MODEL_REQUESTS = False

pytestmark = pytest.mark.no_db

CHART_TEXT = "Chart's up — Dining R13,800 vs Sofas R8,050 (inc VAT)."
DINING_SPEC: dict[str, Any] = {
    "kind": CANVAS_SPEC_KIND,
    "path": CANVAS_PATH,
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
VALID_SKU_ARGS = {
    "our_ref": "QA-COLOUR-1",
    "our_barcode": "QA-COLOUR-1-BAR",
    "name": "QA colour sofa",
    "design": "Nia",
    "fabric": "Linen",
}


@dataclass
class _Appended:
    role: str
    content: str
    structured_payload: Optional[dict[str, Any]]


class _FakeThreads:
    """Records what `_persist_run_result` writes to the thread."""

    def __init__(self) -> None:
        self.appended: list[_Appended] = []
        self.pending_tools: Optional[dict[str, Any]] = None
        self.agent_messages: Optional[list[Any]] = None

    async def append_message(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        role: str,
        content: str,
        *,
        structured_payload: Optional[dict[str, Any]] = None,
    ) -> None:
        self.appended.append(_Appended(role, content, structured_payload))

    async def append_or_replace_needs_ok(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        content: str,
        structured_payload: dict[str, Any],
    ) -> dict[str, Any]:
        if self.appended:
            latest = self.appended[-1]
            existing = latest.structured_payload
            if (
                latest.role == "assistant"
                and isinstance(existing, dict)
                and existing.get("kind") == "needs_ok"
            ):
                kept = richer_needs_ok(existing, structured_payload)
                if kept is structured_payload:
                    self.appended[-1] = _Appended(latest.role, content, structured_payload)
                return kept
        self.appended.append(_Appended("assistant", content, structured_payload))
        return structured_payload

    async def save_agent_state(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        *,
        agent_messages: Optional[list[Any]],
        pending_tools: Optional[dict[str, Any]],
    ) -> None:
        self.agent_messages = agent_messages
        self.pending_tools = pending_tools

    def payloads(self) -> list[Any]:
        return [item.structured_payload for item in self.appended]

    def latest_canvas_payload(self) -> Optional[dict[str, Any]]:
        """What the dock/`/canvas` read: newest canvas payload on the thread."""
        for item in reversed(self.appended):
            payload = item.structured_payload
            if isinstance(payload, dict) and payload.get("kind") in (
                CANVAS_SPEC_KIND,
                "canvas_cleared",
            ):
                return payload
        return None


def _chained_model(second_tool_args: dict[str, Any]) -> FunctionModel:
    """Chart tool then the SKU write tool, both in the first response."""
    calls: list[int] = []

    async def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        if len(calls) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart("chart_dining_vs_sofas", {"mode": "replace"}),
                    ToolCallPart(
                        "run_nia_action",
                        {"action_id": "create_sku", "args": second_tool_args},
                    ),
                ]
            )
        return ModelResponse(parts=[TextPart(CHART_TEXT)])

    return FunctionModel(model_fn)


def _deps() -> NiaDeps:
    return NiaDeps(
        user_id=uuid.uuid4(),
        permissions=[NIA_USE, CATALOGUE_MUTATE],
        page_path="/",
        db=None,
    )


def _service(threads: _FakeThreads) -> NiaRunService:
    service = NiaRunService(None)
    service.threads = threads  # type: ignore[assignment]
    return service


async def _run_chained_turn(
    monkeypatch: pytest.MonkeyPatch,
    sku_args: dict[str, Any],
) -> _FakeThreads:
    async def fake_spec(_db: Any) -> dict[str, Any]:
        return DINING_SPEC

    monkeypatch.setattr("app.nia.tools.build_dining_vs_sofas_canvas_spec", fake_spec)
    deps = _deps()
    result = await nia_agent.run(
        "chart dining vs sofas this month, then help me add a new colour SKU",
        deps=deps,
        model=_chained_model(sku_args),
    )
    threads = _FakeThreads()
    await _service(threads)._persist_run_result(
        user_id=deps.user_id,
        thread_id=uuid.uuid4(),
        user_text="chart dining vs sofas this month, then help me add a new colour SKU",
        result=result,
        deps=deps,
    )
    return threads


async def test_chart_then_sku_form_still_leaves_the_canvas_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chart tool then needs_fields in one run: the chart reaches the thread."""
    threads = await _run_chained_turn(monkeypatch, {})

    assert threads.latest_canvas_payload() == DINING_SPEC
    assert spec_from_thread_payloads(threads.payloads())["components"][0]["id"] == (
        "dining-vs-sofas"
    )
    # The SKU form is still the newest structured card and still pending.
    assert threads.payloads()[-1]["kind"] == "needs_fields"
    assert threads.pending_tools is not None
    assert threads.pending_tools["kind"] == "needs_fields"


async def test_chart_then_sku_approval_still_leaves_the_canvas_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same run ending in needs_ok (approval) must not drop the chart."""
    threads = await _run_chained_turn(monkeypatch, VALID_SKU_ARGS)

    assert threads.latest_canvas_payload() == DINING_SPEC
    assert threads.payloads()[-1]["kind"] == "needs_ok"
    assert threads.pending_tools is not None
    assert threads.pending_tools["kind"] == "needs_ok"


async def test_chart_only_turn_persists_one_canvas_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain chart turn must not gain a duplicate canvas message."""

    async def fake_spec(_db: Any) -> dict[str, Any]:
        return DINING_SPEC

    monkeypatch.setattr("app.nia.tools.build_dining_vs_sofas_canvas_spec", fake_spec)
    calls: list[int] = []

    async def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        if len(calls) == 1:
            return ModelResponse(parts=[ToolCallPart("chart_dining_vs_sofas", {"mode": "replace"})])
        return ModelResponse(parts=[TextPart(CHART_TEXT)])

    deps = _deps()
    result = await nia_agent.run(
        "chart dining vs sofas this month",
        deps=deps,
        model=FunctionModel(model_fn),
    )
    threads = _FakeThreads()
    await _service(threads)._persist_run_result(
        user_id=deps.user_id,
        thread_id=uuid.uuid4(),
        user_text="chart dining vs sofas this month",
        result=result,
        deps=deps,
    )

    canvas_messages = [
        item
        for item in threads.appended
        if isinstance(item.structured_payload, dict)
        and item.structured_payload.get("kind") == CANVAS_SPEC_KIND
    ]
    assert len(canvas_messages) == 1
    assert canvas_messages[0].content == CHART_TEXT
