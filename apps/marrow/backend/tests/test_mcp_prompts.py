from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def _register_prompts(server: FastMCP) -> None:
    from app.mcp import prompts as prompts_mod

    prompts_mod.register_prompts(server)


def test_list_prompts_is_exactly_log_meal_guide() -> None:
    """The public surface used to register no prompts. It now has exactly one:
    ``log_meal_guide`` (meal-logging workflow for clients that surface prompts).
    Anything else appearing here should be a deliberate, reviewed addition.
    """
    server = FastMCP("test")
    _register_prompts(server)
    prompts = server._prompt_manager.list_prompts()
    assert [p.name for p in prompts] == ["log_meal_guide"]
    assert [a.name for a in prompts[0].arguments or []] == ["meal_description"]
