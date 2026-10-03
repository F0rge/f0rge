from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp.observability import instrument_resource
from app.prompts.ingredient_rules import MEAL_LOGGING_GUIDE


def register_meal_guide_resources(server: FastMCP) -> None:
    @server.resource(
        "marrow://reference/meal-logging-guide",
        name="meal_logging_guide",
        description=(
            "How to log meals and ingredients so FODMAP/histamine/gluten/dairy flags work: "
            "decompose composite foods, naming rules, catalogue matching. Not user data."
        ),
        mime_type="text/markdown",
    )
    @instrument_resource("meal_logging_guide")
    async def meal_logging_guide() -> str:
        return MEAL_LOGGING_GUIDE
