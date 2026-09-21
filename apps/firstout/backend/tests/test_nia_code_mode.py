"""Nia Code Mode / Monty wiring (no_db)."""

from __future__ import annotations

import uuid

import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai_harness import CodeMode

import app.nia  # noqa: F401 — register Nia tools on the agent
from app.nia.agent import (
    NIA_CODE_MODE_TOOLS,
    NIA_INSTRUCTIONS,
    NiaDeps,
    nia_agent,
    nia_code_mode_capability,
)
from app.permissions import NIA_USE

models.ALLOW_MODEL_REQUESTS = False

pytestmark = pytest.mark.no_db

NATIVE_TOOLS = (
    "navigate",
    "report_milestone",
    "list_overdue_invoices",
    "get_stock_on_hand",
    "propose_transfer",
    "run_nia_action",
    "list_nia_actions",
)


def test_code_mode_is_wired_on_nia_agent() -> None:
    cap = nia_code_mode_capability()
    assert isinstance(cap, CodeMode)
    assert list(cap.tools) == list(NIA_CODE_MODE_TOOLS)
    assert "`run_code`" in NIA_INSTRUCTIONS
    assert "multi-step calculations" in NIA_INSTRUCTIONS


async def test_run_code_pure_calc_and_native_writes_stay_visible() -> None:
    seen_tools: list[set[str]] = []

    async def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        names = {tool.name for tool in info.function_tools}
        seen_tools.append(names)
        for message in messages:
            for part in message.parts:
                if isinstance(part, ToolReturnPart) and part.tool_name == "run_code":
                    assert part.content == 2
                    return ModelResponse(parts=[TextPart("2")])
        return ModelResponse(parts=[ToolCallPart("run_code", {"code": "1 + 1"})])

    deps = NiaDeps(
        user_id=uuid.uuid4(),
        permissions=[NIA_USE],
        page_path="/",
        db=None,  # type: ignore[arg-type]
    )
    result = await nia_agent.run("add one and one", deps=deps, model=FunctionModel(model_fn))
    assert result.output == "2"
    assert seen_tools
    first = seen_tools[0]
    assert "run_code" in first
    for name in NIA_CODE_MODE_TOOLS:
        assert name not in first
    for name in NATIVE_TOOLS:
        assert name in first
