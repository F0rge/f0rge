from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def _register_prompts(server: FastMCP) -> None:
    from app.mcp import prompts as prompts_mod

    prompts_mod.register_prompts(server)


def test_list_prompts_is_empty() -> None:
    server = FastMCP("test")
    _register_prompts(server)
    assert server._prompt_manager.list_prompts() == []
