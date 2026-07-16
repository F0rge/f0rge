from __future__ import annotations

import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.config import settings
from app.mcp.observability import instrument_resource
from app.mcp.tools._common import _mcp_user_id
from app.models.dietary_ingredient import DietaryIngredient
from app.models.lab_marker_catalog import LabMarkerCatalog
from f0rge_db.tenant import owned_by_user

_MAX_DIETARY_INGREDIENTS = 500


def register_catalog_resources(server: FastMCP) -> None:
    @server.resource(
        "marrow://catalog/lab-markers",
        name="catalog_lab_markers",
        description=(
            "Global reference lab marker catalog: canonical names, display names, and common units. "
            "Load before calling get_lab_history or interpreting lab_markers.canonical_name."
        ),
        mime_type="application/json",
    )
    @instrument_resource("catalog_lab_markers")
    async def catalog_lab_markers() -> dict[str, Any]:
        ref_user_id = uuid.UUID(settings.default_storage_user_id)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(ref_user_id) as db:
            rows = (
                (
                    await db.execute(
                        select(LabMarkerCatalog)
                        .where(owned_by_user(LabMarkerCatalog.user_id))
                        .order_by(LabMarkerCatalog.canonical_name)
                    )
                )
                .scalars()
                .all()
            )

        markers = [
            {
                "canonical_name": row.canonical_name,
                "display_name": row.display_name,
                "common_units": row.common_units,
            }
            for row in rows
        ]
        return {"markers": markers, "count": len(markers)}

    @server.resource(
        "marrow://catalog/dietary-ingredients",
        name="catalog_dietary_ingredients",
        description=(
            "Authenticated user's dietary ingredient catalog (histamine, FODMAP, gluten, dairy). "
            "Load before interpreting photo_ingredients or manual diet flags. Capped at 500 rows."
        ),
        mime_type="application/json",
    )
    @instrument_resource("catalog_dietary_ingredients")
    async def catalog_dietary_ingredients() -> dict[str, Any]:
        user_id = _mcp_user_id(None)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            rows = (
                (
                    await db.execute(
                        select(DietaryIngredient)
                        .where(
                            owned_by_user(DietaryIngredient.user_id),
                            DietaryIngredient.archived.is_(False),
                        )
                        .order_by(DietaryIngredient.canonical_name)
                        .limit(_MAX_DIETARY_INGREDIENTS + 1)
                    )
                )
                .scalars()
                .all()
            )

        truncated = len(rows) > _MAX_DIETARY_INGREDIENTS
        if truncated:
            rows = rows[:_MAX_DIETARY_INGREDIENTS]

        ingredients = [
            {
                "canonical_name": row.canonical_name,
                "category": row.category,
                "histamine_score": row.histamine_score,
                "fodmap_oligos": row.fodmap_oligos,
                "fodmap_fructose": row.fodmap_fructose,
                "fodmap_polyols": row.fodmap_polyols,
                "fodmap_lactose": row.fodmap_lactose,
                "contains_gluten": row.contains_gluten,
                "contains_dairy": row.contains_dairy,
            }
            for row in rows
        ]
        return {
            "ingredients": ingredients,
            "count": len(ingredients),
            "truncated": truncated,
            "limit": _MAX_DIETARY_INGREDIENTS,
        }
