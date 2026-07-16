from __future__ import annotations

import pytest
from mcp.server.fastmcp import FastMCP


def _register_prompts(server: FastMCP) -> None:
    from app.mcp import prompts as prompts_mod

    prompts_mod.register_prompts(server)


def test_list_prompts_returns_at_least_three() -> None:
    server = FastMCP("test")
    _register_prompts(server)

    prompts = server._prompt_manager.list_prompts()
    assert len(prompts) >= 3

    by_name = {prompt.name: prompt for prompt in prompts}
    assert "symptom_diet_correlation" in by_name
    assert "lab_marker_review" in by_name
    assert "daily_checkin_summary" in by_name

    symptom = by_name["symptom_diet_correlation"]
    assert symptom.description
    assert symptom.arguments is not None
    arg_names = {arg.name for arg in symptom.arguments}
    assert arg_names == {"start_date", "end_date"}
    assert all(arg.required for arg in symptom.arguments)

    lab = by_name["lab_marker_review"]
    assert lab.description
    assert lab.arguments is not None
    assert [arg.name for arg in lab.arguments] == ["marker_canonical_name"]
    assert lab.arguments[0].required

    daily = by_name["daily_checkin_summary"]
    assert daily.description
    assert daily.arguments is not None
    assert [arg.name for arg in daily.arguments] == ["date"]
    assert daily.arguments[0].required


@pytest.mark.asyncio
async def test_get_symptom_diet_correlation_references_tools() -> None:
    server = FastMCP("test")
    _register_prompts(server)

    result = await server.get_prompt(
        "symptom_diet_correlation",
        {"start_date": "2025-01-01", "end_date": "2025-01-31"},
    )

    assert result.description
    assert len(result.messages) >= 1

    combined = "\n".join(msg.content.text for msg in result.messages)
    assert "marrow://schema/entries" in combined
    assert "list_entries" in combined
    assert "list_photos_for_entry" in combined
    assert "get_photo_analysis" in combined
    assert "effective_flags" in combined
    assert "Do not diagnose" in combined
    assert "read_sql" in combined


@pytest.mark.asyncio
async def test_invalid_date_returns_clear_validation_error() -> None:
    server = FastMCP("test")
    _register_prompts(server)

    with pytest.raises(ValueError, match="Invalid ISO date for start_date"):
        await server.get_prompt(
            "symptom_diet_correlation",
            {"start_date": "not-a-date", "end_date": "2025-01-31"},
        )
