from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.crud.dietary_ingredient_catalog import DietaryIngredientCRUD
from app.mcp.ingredient_catalog import catalog_item_payload
from app.mcp.observability import instrument_resource
from app.mcp.tools._common import _mcp_user_id

# Same order of magnitude as the vision-prompt catalogue context (catalog_context.py).
DIETARY_CATALOG_RESOURCE_MAX = 500


def register_dietary_catalog_resources(server: FastMCP) -> None:
    @server.resource(
        "marrow://catalog/dietary-ingredients",
        name="catalog_dietary_ingredients",
        description=(
            "The caller's own ingredient catalogue (active entries only): canonical_name, aliases "
            "and FODMAP/histamine/gluten/dairy flags. Read before log_meal or set_ingredients and "
            "use canonical_name exactly; aliases are recognition aids, never ingredient names. "
            "Per user; capped at 500 entries (alphabetical)."
        ),
        mime_type="application/json",
    )
    @instrument_resource("catalog_dietary_ingredients")
    async def catalog_dietary_ingredients() -> dict[str, Any]:
        user_id = _mcp_user_id(None)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            rows = await DietaryIngredientCRUD(db).list(
                include_archived=False, limit=DIETARY_CATALOG_RESOURCE_MAX + 1
            )
            truncated = len(rows) > DIETARY_CATALOG_RESOURCE_MAX
            ingredients = [catalog_item_payload(row) for row in rows[:DIETARY_CATALOG_RESOURCE_MAX]]
        return {
            "ingredients": ingredients,
            "count": len(ingredients),
            "truncated": truncated,
            "note": (
                "Use canonical_name exactly when logging ingredients. "
                "Archived ingredients are not listed."
            ),
        }
