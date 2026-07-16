from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import select

from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id, _validate_date
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from f0rge_db.tenant import owned_by_user


def _ingredient_to_dict(row: PhotoIngredient) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "canonical_name": row.canonical_name,
        "visible": row.visible,
        "confidence": row.confidence,
        "user_edited": row.user_edited,
        "histamine_score": row.histamine_score,
        "fodmap_oligos": row.fodmap_oligos,
        "fodmap_fructose": row.fodmap_fructose,
        "fodmap_polyols": row.fodmap_polyols,
        "fodmap_lactose": row.fodmap_lactose,
        "contains_gluten": row.contains_gluten,
        "contains_dairy": row.contains_dairy,
    }


def _analysis_to_dict(analysis: PhotoAnalysis, photo_id: int) -> dict[str, Any]:
    return {
        "id": analysis.id,
        "photo_id": photo_id,
        "status": analysis.status,
        "dish_name": analysis.dish_name,
        "cuisine": analysis.cuisine,
        "dish_confidence": analysis.dish_confidence,
        "ingredients": [_ingredient_to_dict(i) for i in analysis.ingredients],
        "error_message": analysis.error_message,
        "gluten_free_confirmed": analysis.gluten_free_confirmed,
        "lactose_free_confirmed": analysis.lactose_free_confirmed,
        "created_at": analysis.created_at.isoformat(),
        "updated_at": analysis.updated_at.isoformat(),
    }


def register_food_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("get_photo_analysis")
    async def get_photo_analysis(photo_id: int, ctx: Context = None) -> Optional[dict[str, Any]]:
        """Fetch food analysis for one photo: dish, status, ingredients with diet fields.

        Returns null when the photo or its analysis is missing. Prefer this over
        get_entry when you need ingredient-level histamine/FODMAP/gluten/dairy detail.
        Use search_health_data for semantic lookup across meals; get_entry for daily
        symptom scores and effective diet flags only.
        """
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            analysis = await PhotoAnalysisCRUD(db).get_for_photo_with_ingredients(photo_id)
        if analysis is None:
            return None
        return _analysis_to_dict(analysis, photo_id)

    @server.tool()
    @instrument_tool("list_photos_for_entry")
    async def list_photos_for_entry(date: str, ctx: Context = None) -> dict[str, Any]:
        """List meal photos for an entry date (YYYY-MM-DD).

        Returns photo ids, labels, meal_time, and analysis status. Does not include
        image bytes. Use get_photo_analysis for ingredient detail; get_entry for
        symptom scores on the same day.
        """
        parsed = _validate_date(date, "date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(Photo, PhotoAnalysis.status)
                .join(Entry, Photo.entry_id == Entry.id)
                .outerjoin(PhotoAnalysis, Photo.meal_id == PhotoAnalysis.meal_id)
                .where(owned_by_user(Photo.user_id), Entry.date == parsed)
                .order_by(Photo.meal_time.asc().nulls_last(), Photo.id.asc())
            )
            rows = (await db.execute(stmt)).all()

        photos = []
        for photo, analysis_status in rows:
            photos.append(
                {
                    "id": photo.id,
                    "label": photo.label,
                    "meal_time": photo.meal_time.isoformat() if photo.meal_time else None,
                    "analysis_status": analysis_status,
                }
            )
        return {"date": str(parsed), "photos": photos}
