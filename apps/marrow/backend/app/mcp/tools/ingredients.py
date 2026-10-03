from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from f0rge_core.exceptions import ValidationError
from app.mcp.ingredient_catalog import catalog_item_flags
from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id
from app.services.ingredient_matching import analyse, looks_composite
from app.services.ingredient_resolver import COMPOSITE_HINT, IngredientResolver

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 25

_SEARCH_DESCRIPTION = (
    "Find ingredients in the caller's own catalogue (active entries only) and return their exact "
    "canonical_name, match_type (exact, alias, normalised, token_subset, fuzzy, partial, prefix), "
    "score and flags (FODMAP axes, histamine, gluten, dairy). Call this for each constituent "
    "ingredient before log_meal or set_ingredients and send canonical_name exactly; aliases only "
    "help you find the entry. Only exact, alias and normalised matches are the same ingredient - "
    "other types are suggestions. Results are ranked best first. If nothing fits, use a plain "
    "lowercase name: it is stored without flags and never added to the catalogue."
)


def register_ingredients_tools(server: FastMCP) -> None:
    @server.tool(description=_SEARCH_DESCRIPTION)
    @instrument_tool("search_ingredients")
    async def search_ingredients(
        query: str, limit: int = DEFAULT_SEARCH_LIMIT, ctx: Context = None
    ) -> dict[str, Any]:
        if not query or not query.strip():
            raise ValidationError("query is required")
        capped = max(1, min(int(limit), MAX_SEARCH_LIMIT))
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            resolver = await IngredientResolver.for_current_user(db)
        candidates = resolver.matcher.match(query, limit=capped)
        results = [
            {
                "canonical_name": c.entry.canonical_name,
                "matched_alias": c.matched_alias,
                "match_type": c.match_type,
                "score": c.score,
                "category": c.entry.category,
                "flags": catalog_item_flags(c.entry),
            }
            for c in candidates
        ]
        payload: dict[str, Any] = {
            "query": query.strip(),
            "results": results,
            "count": len(results),
            "note": (
                "Send canonical_name exactly. Only exact/alias/normalised matches are the same "
                "ingredient; other match types are suggestions."
            ),
        }
        if looks_composite(analyse(query)):
            payload["composite_suspected"] = True
            payload["composite_hint"] = COMPOSITE_HINT
        if not results:
            payload["note"] = (
                "No catalogue entry is close. Use a plain lowercase common name; it will be "
                "stored without flags (never added to the catalogue automatically)."
            )
        return payload
