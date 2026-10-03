from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.prompts.ingredient_rules import MEAL_LOGGING_GUIDE


def register_prompts(server: FastMCP) -> None:
    """Public Marrow MCP prompt: one workflow guide, for clients that surface prompts."""

    @server.prompt(
        name="log_meal_guide",
        description=(
            "Step-by-step guide to log a meal with correctly decomposed, catalogue-matched "
            "ingredients."
        ),
    )
    def log_meal_guide(meal_description: str = "") -> str:
        text = MEAL_LOGGING_GUIDE
        if meal_description.strip():
            text += (
                "\n## Meal to log now\n"
                f"{meal_description.strip()}\n\n"
                "Follow the workflow above for this meal. Show the user the ingredient list "
                "(marking inferred ones) before calling log_meal."
            )
        return text
