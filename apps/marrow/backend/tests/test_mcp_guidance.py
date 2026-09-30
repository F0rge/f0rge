"""MCP guidance surfaces: server instructions, tool descriptions, guide resource, prompt."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp import tools as t_mod
from app.mcp.prompts import register_prompts
from app.mcp.resources import register_resources
from app.mcp.server import create_server, register_all
from app.prompts.ingredient_rules import (
    COMPOSITE_PRODUCT_RULES,
    INGREDIENT_TOOL_NOTE,
    MCP_SERVER_INSTRUCTIONS,
)


def _tool_descriptions() -> dict[str, str]:
    server = FastMCP("test")
    t_mod.register_tools(server)
    return {t.name: t.description for t in server._tool_manager.list_tools()}


def test_server_instructions_include_shared_rules() -> None:
    server = create_server()
    assert server.instructions == MCP_SERVER_INSTRUCTIONS
    assert COMPOSITE_PRODUCT_RULES in server.instructions
    assert "marrow://reference/meal-logging-guide" in server.instructions
    assert "marrow://catalog/dietary-ingredients" in server.instructions


def test_register_all_exposes_guidance_end_to_end() -> None:
    server = create_server()
    register_all(server)
    assert {p.name for p in server._prompt_manager.list_prompts()} == {"log_meal_guide"}
    uris = {str(r.uri) for r in server._resource_manager.list_resources()}
    assert "marrow://reference/meal-logging-guide" in uris
    assert "marrow://catalog/dietary-ingredients" in uris


def test_meal_tool_descriptions_carry_ingredient_guidance() -> None:
    descriptions = _tool_descriptions()
    for name in ("log_meal", "set_ingredients"):
        assert INGREDIENT_TOOL_NOTE in descriptions[name], name
        assert "marrow://catalog/dietary-ingredients" in descriptions[name], name
    assert descriptions["log_meal"].startswith("Log a meal on a day.")
    assert descriptions["set_ingredients"].startswith("Replace the whole ingredient list")
    assert "set_ingredients" in descriptions["edit_meal"]
    assert "ingredient" in descriptions["edit_meal"]


def test_other_tool_descriptions_are_unchanged() -> None:
    descriptions = _tool_descriptions()
    assert descriptions["get_meal"].startswith("One meal:")
    assert "ingredient" not in descriptions["delete_meal"].lower()


async def test_meal_logging_guide_resource_content() -> None:
    server = FastMCP("test")
    register_resources(server)
    contents = await server.read_resource("marrow://reference/meal-logging-guide")
    text = contents[0].content
    assert isinstance(text, str)
    assert "Auchan" in text and "oats" in text
    assert "brand" in text.lower()
    assert "{{" not in text


async def test_log_meal_guide_prompt_renders_with_and_without_description() -> None:
    server = FastMCP("test")
    register_prompts(server)
    plain = await server.get_prompt("log_meal_guide")
    plain_text = plain.messages[0].content.text
    assert "Logging meals with ingredients" in plain_text
    assert "Meal to log now" not in plain_text

    custom = await server.get_prompt("log_meal_guide", {"meal_description": "40 g muesli"})
    custom_text = custom.messages[0].content.text
    assert "Meal to log now" in custom_text
    assert "40 g muesli" in custom_text
