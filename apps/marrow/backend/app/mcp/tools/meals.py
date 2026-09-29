from __future__ import annotations

import asyncio
import base64
import datetime
from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP
from app.crud.meal_tags import MealTagCRUD
from app.crud.meals import MealCRUD
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from app.mcp.observability import instrument_tool
from app.mcp.tools._common import (
    _analysis_to_dict,
    _ingredient_to_dict,
    _mcp_user_id,
    _validate_date,
)
from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.food_analysis import IngredientCreate
from app.services.entries import get_or_create_entry
from app.services.food_analysis import FoodAnalysisService
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.ingredient_lookup import IngredientLookupService
from app.services.meal_tags import MealTagService
from app.services.photo_storage import resize_image, save_photo, thumb_filename
from app.services.photos import entry_photo_upload_lock, next_photo_filename
from app.crud.base import unit_of_work
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.tenant import current_user_id


async def _tags_for_photo(db, photo_id: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tag in await MealTagCRUD(db).list_for_source_photo(photo_id):
        user = await MealTagService(db).social_crud.get_by_id(tag.tagged_user_id)
        handle = user.handle if user is not None else ""
        items.append({"handle": handle, "status": tag.status})
    return items


def register_meals_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("get_meal")
    async def get_meal(photo_id: int, ctx: Context = None) -> Optional[dict[str, Any]]:
        """One meal: name, time, ingredients, people tags, and photo metadata."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            photo = await PhotoCRUD(db).get_by_id_owned(photo_id)
            if photo is None:
                return None
            analysis = await PhotoAnalysisCRUD(db).get_for_photo_with_ingredients(photo_id)
            tags = await _tags_for_photo(db, photo_id)
            entry_date = str(photo.entry.date)
            name = photo.label
            if analysis is not None and analysis.dish_name:
                name = name or analysis.dish_name
            payload: dict[str, Any] = {
                "photo_id": photo.id,
                "meal_id": photo.meal_id,
                "date": entry_date,
                "name": name,
                "meal_time": photo.meal_time.isoformat() if photo.meal_time else None,
                "has_photo": photo.filename is not None,
                "tags": tags,
            }
            if analysis is not None:
                payload["analysis"] = _analysis_to_dict(analysis, photo_id)
            else:
                payload["ingredients"] = []
            return payload

    @server.tool()
    @instrument_tool("log_meal")
    async def log_meal(
        date: str,
        name: str,
        meal_time: Optional[str] = None,
        ingredients: Optional[list[str]] = None,
        photo_base64: Optional[str] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Log a meal on a day. Returns when the meal row exists (no background vision)."""
        parsed = _validate_date(date, "date")
        if not name.strip():
            raise ValidationError("name is required")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        effective_time: datetime.datetime
        if meal_time:
            try:
                if "T" in meal_time:
                    effective_time = datetime.datetime.fromisoformat(meal_time)
                else:
                    hh, mm = meal_time.split(":", 1)
                    effective_time = datetime.datetime(
                        parsed.year, parsed.month, parsed.day, int(hh), int(mm)
                    )
            except ValueError as exc:
                raise ValidationError("meal_time must be ISO datetime or HH:MM") from exc
        else:
            effective_time = datetime.datetime.utcnow()

        if effective_time.tzinfo is not None:
            offset = effective_time.utcoffset()
            effective_time = (effective_time - offset).replace(tzinfo=None)

        ingredient_names = [i.strip() for i in (ingredients or []) if i and i.strip()]

        async with mcp_tools.scoped_main_session(user_id) as db:
            async with unit_of_work(db):
                entry = await get_or_create_entry(db, parsed)
                now = datetime.datetime.utcnow()
                meal = Meal(
                    owner_user_id=current_user_id(),
                    filename=None,
                    label=name.strip(),
                    meal_time=effective_time,
                    created_at=now,
                )
                await MealCRUD(db).add_and_flush(meal)
                photo = Photo(
                    user_id=current_user_id(),
                    entry_id=entry.id,
                    meal_id=meal.id,
                    filename=None,
                    label=name.strip(),
                    meal_time=effective_time,
                    created_at=now,
                )
                PhotoCRUD(db).add(photo)
                await db.flush()

                analysis = PhotoAnalysis(
                    user_id=current_user_id(),
                    meal_id=meal.id,
                    photo_id=photo.id,
                    status="confirmed",
                    dish_name=name.strip(),
                    dish_confidence=1.0,
                )
                PhotoAnalysisCRUD(db).add(analysis)
                await db.flush()

                lookup = IngredientLookupService(db)
                ingredient_crud = PhotoIngredientCRUD(db)
                for label in ingredient_names:
                    match = await lookup.lookup(label)
                    ingredient_crud.add(
                        PhotoIngredient(
                            user_id=current_user_id(),
                            analysis_id=analysis.id,
                            name=label,
                            canonical_name=match.canonical_name if match else None,
                            visible=True,
                            confidence=1.0,
                            user_edited=True,
                            histamine_score=match.histamine_score if match else None,
                            fodmap_oligos=match.fodmap_oligos if match else None,
                            fodmap_fructose=match.fodmap_fructose if match else None,
                            fodmap_polyols=match.fodmap_polyols if match else None,
                            fodmap_lactose=match.fodmap_lactose if match else None,
                            contains_gluten=match.contains_gluten if match else None,
                            contains_dairy=match.contains_dairy if match else None,
                        )
                    )

                if photo_base64:
                    raw = base64.b64decode(photo_base64, validate=True)
                    processed = await asyncio.to_thread(resize_image, raw)
                    async with entry_photo_upload_lock(db, entry.id):
                        filename = await next_photo_filename(db, entry)
                        await asyncio.to_thread(
                            save_photo, processed, filename, user_id=str(current_user_id())
                        )
                        thumb = await asyncio.to_thread(resize_image, processed, max_dim=256)
                        await asyncio.to_thread(
                            save_photo,
                            thumb,
                            thumb_filename(filename),
                            user_id=str(current_user_id()),
                        )
                        photo.filename = filename
                        meal.filename = filename

        return {
            "photo_id": photo.id,
            "meal_id": meal.id,
            "date": str(parsed),
            "name": name.strip(),
            "meal_time": effective_time.isoformat(),
            "ingredient_count": len(ingredient_names),
            "has_photo": photo.filename is not None,
        }

    @server.tool()
    @instrument_tool("edit_meal")
    async def edit_meal(
        photo_id: int,
        name: Optional[str] = None,
        meal_time: Optional[str] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Update a meal's display name and/or meal time."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            photo = await PhotoCRUD(db).get_by_id_owned(photo_id)
            if photo is None:
                raise NotFoundError(f"Meal photo {photo_id} not found")
            if name is not None:
                stripped = name.strip() or None
                photo.label = stripped
                if photo.meal is not None:
                    photo.meal.label = stripped
                analysis = await PhotoAnalysisCRUD(db).get_for_photo(photo_id)
                if analysis is not None and stripped:
                    analysis.dish_name = stripped
            if meal_time is not None:
                try:
                    parsed_time = datetime.datetime.fromisoformat(meal_time)
                except ValueError as exc:
                    raise ValidationError("meal_time must be ISO datetime") from exc
                if parsed_time.tzinfo is not None:
                    offset = parsed_time.utcoffset()
                    parsed_time = (parsed_time - offset).replace(tzinfo=None)
                photo.meal_time = parsed_time
                if photo.meal is not None:
                    photo.meal.meal_time = parsed_time
            await PhotoCRUD(db).commit_refresh(photo)
            return {
                "photo_id": photo.id,
                "name": photo.label,
                "meal_time": photo.meal_time.isoformat() if photo.meal_time else None,
            }

    @server.tool()
    @instrument_tool("set_ingredients")
    async def set_ingredients(
        photo_id: int,
        ingredients: list[str],
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Replace the ingredient list on a meal (confirmed analysis)."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            analysis = await PhotoAnalysisCRUD(db).get_for_photo_with_ingredients(photo_id)
            if analysis is None:
                raise NotFoundError("No meal analysis for this photo")
            service = FoodAnalysisService(db, FoodAnalysisOrchestrator())
            for ing in list(analysis.ingredients):
                await service.delete_ingredient(ing.id)
            created: list[dict[str, Any]] = []
            for label in ingredients:
                if not label.strip():
                    continue
                row = await service.add_ingredient(
                    analysis.id, IngredientCreate(name=label.strip())
                )
                created.append(_ingredient_to_dict(row))
            return {"photo_id": photo_id, "ingredients": created}

    @server.tool()
    @instrument_tool("tag_meal")
    async def tag_meal(
        photo_id: int,
        handles: list[str],
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Set who is tagged on a meal. Pass an empty list to clear pending tags."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            tag_service = MealTagService(db)
            photo = await PhotoCRUD(db).get_by_id_owned(photo_id)
            if photo is None:
                raise NotFoundError("Photo not found")
            for tag in await tag_service.crud.list_for_source_photo(photo_id):
                if tag.status in ("pending_analysis", "pending_approval"):
                    await tag_service.cancel(tag.id)
            if handles:
                await tag_service.add_tags_to_photo(photo_id, handles)
            tags = await _tags_for_photo(db, photo_id)
            return {"photo_id": photo_id, "tags": tags}

    @server.tool()
    @instrument_tool("delete_meal")
    async def delete_meal(photo_id: int, ctx: Context = None) -> dict[str, Any]:
        """Delete a meal (photo placement) and its files."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools
        from app.services.photos import PhotoService

        async with mcp_tools.scoped_main_session(user_id) as db:
            photo_service = PhotoService(db, FoodAnalysisOrchestrator(), MealTagService(db))
            await photo_service.delete(photo_id)

        return {"photo_id": photo_id, "deleted": True}
