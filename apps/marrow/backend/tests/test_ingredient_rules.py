"""Shared ingredient-logging rules: import-free, Jinja-safe, and wired into the MCP surface."""

from __future__ import annotations

import ast
from pathlib import Path

from app.prompts import ingredient_rules as rules

_MODULE_PATH = Path(rules.__file__)

_ALL_TEXT = {
    name: getattr(rules, name)
    for name in (
        "INGREDIENT_NAMING_RULES",
        "COMPOSITE_PRODUCT_RULES",
        "CATALOG_MATCHING_RULES",
        "EVIDENCE_RULES",
        "MEAL_LOGGING_GUIDE",
        "INGREDIENT_TOOL_NOTE",
        "MCP_SERVER_INSTRUCTIONS",
    )
}


def test_module_is_import_free() -> None:
    """The DAG may load this file by path later, so it must not import anything."""
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert [ast.unparse(node) for node in imports] == ["from __future__ import annotations"]


def test_text_is_safe_for_jinja_templates() -> None:
    for name, text in _ALL_TEXT.items():
        assert "{{" not in text, name
        assert "{%" not in text, name
        assert "{#" not in text, name


def test_rules_cover_decomposition_naming_and_evidence() -> None:
    composite = rules.COMPOSITE_PRODUCT_RULES.lower()
    assert "muesli" in composite and "bread" in composite and "ready meals" in composite
    assert "ingredient list" in composite
    naming = rules.INGREDIENT_NAMING_RULES.lower()
    assert "brand" in naming and "pack size" in naming and "quantity" in naming
    assert "lowercase" in naming and "singular" in naming
    evidence = rules.EVIDENCE_RULES.lower()
    assert "do not invent" in evidence and "inferred" in evidence


def test_rules_only_reference_tools_and_resources_that_exist() -> None:
    """search_ingredients arrives in a later change; guidance must not promise it yet."""
    from mcp.server.fastmcp import FastMCP

    from app.mcp import resources as resources_mod
    from app.mcp import tools as tools_mod

    server = FastMCP("test")
    tools_mod.register_tools(server)
    resources_mod.register_resources(server)
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    resource_uris = {str(r.uri) for r in server._resource_manager.list_resources()}

    for name, text in _ALL_TEXT.items():
        for word in text.replace("`", " ").replace("(", " ").replace(")", " ").split():
            if word.startswith("marrow://"):
                assert word.rstrip(".,;") in resource_uris, (name, word)
        if "search_ingredients" in text:
            assert "search_ingredients" in tool_names, name
