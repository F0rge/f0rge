from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp.observability import instrument_resource
from app.prompts.ingredient_rules import MEAL_LOGGING_GUIDE

# Agent recipe for attaching a photo. Kept out of ingredient_rules so the
# Jinja-bound classifier prompt stays free of this filesystem workflow.
MEAL_PHOTO_RECIPE = """\
## Meal photos
1. Image = the path in the chat message, else the newest jpg/png/webp/heic in \
/home/box/agent-data/agents/<self-id>/attachments/ modified in the last 15 min.
2. base64 -w0 "$IMG" > /workspace/tmp/meal-<sha>.b64 (no resizing).
3. log_meal(..., photo_base64="$file:/workspace/tmp/meal-<sha>.b64"); if has_photo is \
false, call attach_meal_photo(photo_id, photo_base64="$file:..."); delete the .b64.
4. Reuse: log_meal(..., source_photo_id=790) or attach_meal_photo(742, source_photo_id=790).
"""


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
        return MEAL_LOGGING_GUIDE + "\n" + MEAL_PHOTO_RECIPE
