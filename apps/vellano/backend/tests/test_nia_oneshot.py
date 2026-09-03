"""Nia one-shot chart + SKU in the same turn (#613 Q7)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings
from app.nia.canvas import ranking_text_from_canvas_spec, spec_from_thread_payloads
from app.nia.oneshot import (
    chart_kind_for_compound_prompt,
    is_compound_chart_write,
    should_persist_canvas_ahead,
)
import app.nia  # noqa: F401 — register tools

models.ALLOW_MODEL_REQUESTS = False

COMPOUND_PROMPT = "chart dining vs sofas / best-sellers, then draft a new colour SKU"
SKU_ONLY_PROMPT = "create sku"


class ArgsTestModel(TestModel):
    """TestModel that calls one tool with fixed arguments."""

    def __init__(self, tool_name: str, tool_args: dict, **kwargs) -> None:
        self._fixed_tool_name = tool_name
        self._fixed_tool_args = tool_args
        super().__init__(call_tools=[tool_name], **kwargs)

    def gen_tool_args(self, tool_def):
        if tool_def.name == self._fixed_tool_name:
            return self._fixed_tool_args
        return super().gen_tool_args(tool_def)


class MultiArgsTestModel(TestModel):
    """TestModel that calls several tools with fixed arguments in one turn."""

    def __init__(self, tool_args_by_name: dict, **kwargs) -> None:
        self._fixed = tool_args_by_name
        super().__init__(call_tools=list(tool_args_by_name.keys()), **kwargs)

    def gen_tool_args(self, tool_def):
        if tool_def.name in self._fixed:
            return self._fixed[tool_def.name]
        return super().gen_tool_args(tool_def)


@pytest.fixture(autouse=True)
def openrouter_key_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def _consume_stream(resp) -> bytes:
    chunks: list[bytes] = []
    async for chunk in resp.aiter_bytes():
        chunks.append(chunk)
    return b"".join(chunks)


async def _create_thread(client: AsyncClient) -> str:
    create = await client.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    return create.json()["id"]


def _payloads(messages: list[dict]) -> list[dict]:
    return [m["structured_payload"] for m in messages if m.get("structured_payload")]


def _kinds(messages: list[dict]) -> list[str]:
    return [payload.get("kind") for payload in _payloads(messages) if payload.get("kind")]


def _write_only_sku_model() -> ArgsTestModel:
    return ArgsTestModel("run_nia_action", {"action_id": "create_sku", "args": {}})


@pytest.mark.no_db
def test_matcher_compound_vs_sku_only() -> None:
    assert is_compound_chart_write(COMPOUND_PROMPT) is True
    assert chart_kind_for_compound_prompt(COMPOUND_PROMPT) == "dining_vs_sofas"
    assert is_compound_chart_write(SKU_ONLY_PROMPT) is False
    assert chart_kind_for_compound_prompt(SKU_ONLY_PROMPT) is None
    assert chart_kind_for_compound_prompt("chart best-sellers then draft a new colour SKU") == (
        "sales_by_sku"
    )
    assert chart_kind_for_compound_prompt("chart then create sku") == "dining_vs_sofas"


@pytest.mark.no_db
def test_ranking_text_from_dining_vs_sofas() -> None:
    spec = {
        "kind": "canvas_spec",
        "path": "/canvas",
        "title": "Dining vs sofas this month",
        "components": [
            {
                "type": "bar",
                "id": "dining-vs-sofas",
                "title": "Sales this month (ZAR inc VAT)",
                "categories": ["Dining", "Sofas"],
                "series": [{"name": "Sales", "values": [1150.0, 2300.0]}],
            }
        ],
    }
    assert ranking_text_from_canvas_spec(spec) == "Dining R1150.00 vs sofas R2300.00 this month."


@pytest.mark.no_db
def test_hydrate_sees_canvas_when_fields_is_last() -> None:
    canvas = {
        "kind": "canvas_spec",
        "path": "/canvas",
        "title": "Dining vs sofas this month",
        "components": [
            {
                "type": "bar",
                "id": "dining-vs-sofas",
                "title": "Sales",
                "categories": ["Dining", "Sofas"],
                "series": [{"name": "Sales", "values": [0.0, 0.0]}],
            }
        ],
    }
    fields = {"kind": "needs_fields", "action_id": "create_sku"}
    hydrated = spec_from_thread_payloads([canvas, fields])
    assert hydrated["kind"] == "canvas_spec"
    assert hydrated["components"][0]["id"] == "dining-vs-sofas"


@pytest.mark.no_db
def test_persist_canvas_ahead_only_for_non_canvas_cards() -> None:
    ahead = SimpleNamespace(canvas_updated=True)
    skip = SimpleNamespace(canvas_updated=False)
    assert should_persist_canvas_ahead(ahead, {"kind": "needs_fields"}) is True
    assert should_persist_canvas_ahead(ahead, {"kind": "needs_ok"}) is True
    assert should_persist_canvas_ahead(ahead, {"kind": "canvas_spec"}) is False
    assert should_persist_canvas_ahead(skip, {"kind": "needs_fields"}) is False


async def test_compound_prompt_write_only_model_keeps_chart_and_fields(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        _write_only_sku_model,
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": COMPOUND_PROMPT},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    messages = thread.json()["messages"]
    kinds = _kinds(messages)
    assert "canvas_spec" in kinds
    assert "needs_fields" in kinds or "needs_ok" in kinds

    last_assistant = [m for m in messages if m["role"] == "assistant"][-1]
    last_kind = (last_assistant.get("structured_payload") or {}).get("kind")
    assert last_kind in ("needs_fields", "needs_ok")

    hydrated = spec_from_thread_payloads([m.get("structured_payload") for m in messages])
    assert hydrated["kind"] == "canvas_spec"
    assert hydrated["components"]
    assert hydrated["components"][0]["id"] == "dining-vs-sofas"


async def test_sku_only_prompt_does_not_auto_add_chart(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        _write_only_sku_model,
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": SKU_ONLY_PROMPT},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    kinds = _kinds(thread.json()["messages"])
    assert "canvas_spec" not in kinds
    assert "needs_fields" in kinds


async def test_chart_then_write_keeps_both(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: MultiArgsTestModel(
            {
                "chart_dining_vs_sofas": {"mode": "replace"},
                "run_nia_action": {"action_id": "create_sku", "args": {}},
            }
        ),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": COMPOUND_PROMPT},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    messages = thread.json()["messages"]
    kinds = _kinds(messages)
    assert "canvas_spec" in kinds
    assert "needs_fields" in kinds or "needs_ok" in kinds
    last_assistant = [m for m in messages if m["role"] == "assistant"][-1]
    assert (last_assistant.get("structured_payload") or {}).get("kind") in (
        "needs_fields",
        "needs_ok",
    )
    hydrated = spec_from_thread_payloads([m.get("structured_payload") for m in messages])
    assert hydrated["components"][0]["id"] == "dining-vs-sofas"
