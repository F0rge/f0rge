from __future__ import annotations

import datetime
from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP
from app.crud.entries import EntryCRUD
from app.crud.meal_tags import MealTagCRUD
from app.crud.meals import MealCRUD
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photos import PhotoCRUD
from app.mcp.ingredient_logging import (
    ingredient_payload,
    next_step,
    resolve_for_current_user,
    stage_ingredient_rows,
    summary_fields,
)
from app.mcp.meal_photos import (
    copy_photo_bytes,
    decode_photo_b64,
    delete_photo_files,
    filename_in_use,
    find_duplicate,
    photo_hash_tag,
    photo_sha256_value,
    placement_count,
    store_photo_for,
)
from app.mcp.observability import instrument_tool
from app.mcp.tools._common import (
    _analysis_to_dict,
    _mcp_user_id,
    _validate_date,
)
from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.services.entries import get_or_create_entry
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.meal_tags import MealTagService
from app.services.photo_storage import thumb_filename
from app.prompts.ingredient_rules import INGREDIENT_TOOL_NOTE
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


_LOG_MEAL_DESCRIPTION = (
    "Log a meal on a day. Returns when the meal row exists (no background vision). "
    "`name` is the meal/product name and may carry brand, pack size and quantity. "
    "Optional photo_base64 (JPEG/PNG/WebP/HEIC; server converts to JPEG <=2048px, max 25 MB) "
    "or source_photo_id to copy another meal's image; the two are mutually exclusive. "
    "The same image on the same day returns the existing meal (deduplicated) unless "
    "allow_duplicate is true. " + INGREDIENT_TOOL_NOTE
)
_ATTACH_MEAL_PHOTO_DESCRIPTION = (
    "Attach or replace the image on an existing meal: photo_base64 "
    "(JPEG/PNG/WebP/HEIC, server converts to JPEG <=2048px, max 25 MB) or "
    "source_photo_id to copy another meal's image."
)
_SET_INGREDIENTS_DESCRIPTION = (
    "Replace the whole ingredient list on an existing meal (confirmed analysis). "
    + INGREDIENT_TOOL_NOTE
)


async def _deduped_meal_result(
    db, photo: Photo, parsed: datetime.date, hash_tag: str
) -> dict[str, Any]:
    """Return the existing same-day meal. Creates no rows."""
    analysis = await PhotoAnalysisCRUD(db).get_for_photo_with_ingredients(photo.id)
    stored = list(analysis.ingredients) if analysis is not None else []
    names = [row.name for row in stored]
    resolutions, dropped = await resolve_for_current_user(db, names)
    result_ingredients = [
        ingredient_payload(row, resolution) for row, resolution in zip(stored, resolutions)
    ]
    return {
        "photo_id": photo.id,
        "meal_id": photo.meal_id,
        "date": str(parsed),
        "name": photo.label,
        "meal_time": photo.meal_time.isoformat() if photo.meal_time else None,
        **summary_fields(resolutions, dropped),
        "ingredients": result_ingredients,
        "next_step": "Existing meal reused (same image already logged this day).",
        "has_photo": photo.filename is not None,
        "photo_sha256": hash_tag,
        "deduplicated": True,
    }


def _image_hash_matches(photo: Photo, hash_tag: str) -> bool:
    if photo.original_filename == hash_tag:
        return True
    meal = photo.meal
    return meal is not None and meal.original_filename == hash_tag


_EDIT_MEAL_DESCRIPTION = (
    "Update a meal's display name and/or meal time. Does not change ingredients: "
    "use search_ingredients then set_ingredients for that (decomposed, catalogue-matched "
    "names; see marrow://reference/meal-logging-guide)."
)


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
                "photo_sha256": photo_sha256_value(photo.original_filename),
                "photo_created_at": photo.created_at.isoformat() if photo.created_at else None,
                "tags": tags,
            }
            if analysis is not None:
                payload["analysis"] = _analysis_to_dict(analysis, photo_id)
            else:
                payload["ingredients"] = []
            return payload

    @server.tool(description=_LOG_MEAL_DESCRIPTION)
    @instrument_tool("log_meal")
    async def log_meal(
        date: str,
        name: str,
        meal_time: Optional[str] = None,
        ingredients: Optional[list[str]] = None,
        photo_base64: Optional[str] = None,
        source_photo_id: Optional[int] = None,
        allow_duplicate: bool = False,
        ctx: Context = None,
    ) -> dict[str, Any]:
        parsed = _validate_date(date, "date")
        if not name.strip():
            raise ValidationError("name is required")
        if photo_base64 is not None and source_photo_id is not None:
            raise ValidationError("pass photo_base64 or source_photo_id, not both")
        # Decode before any write so a bad image creates no meal.
        raw: Optional[bytes] = decode_photo_b64(photo_base64) if photo_base64 is not None else None
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

        async with mcp_tools.scoped_main_session(user_id) as db:
            if source_photo_id is not None:
                src = await PhotoCRUD(db).get_by_id_owned(source_photo_id)
                if src is None:
                    raise NotFoundError(f"Meal photo {source_photo_id} not found")
                raw = await copy_photo_bytes(src, user_id)
            hash_tag = photo_hash_tag(raw) if raw is not None else None

            # Resolve (and validate) before any write so a bad request creates no meal.
            resolutions, dropped = await resolve_for_current_user(db, ingredients or [])

            if hash_tag is not None and source_photo_id is None and not allow_duplicate:
                existing_entry = await EntryCRUD(db).get_by_date(parsed)
                if existing_entry is not None:
                    duplicate = await find_duplicate(db, existing_entry.id, hash_tag)
                    if duplicate is not None:
                        return await _deduped_meal_result(db, duplicate, parsed, hash_tag)

            saved: list[str] = []
            try:
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

                    rows = stage_ingredient_rows(
                        db.add, resolutions, user_id=current_user_id(), analysis_id=analysis.id
                    )

                    if raw is not None:
                        saved = await store_photo_for(db, entry, photo, meal, raw, user_id)
            except Exception:
                await delete_photo_files(saved, user_id)
                raise

            result_ingredients = [
                ingredient_payload(row, resolution) for row, resolution in zip(rows, resolutions)
            ]

        return {
            "photo_id": photo.id,
            "meal_id": meal.id,
            "date": str(parsed),
            "name": name.strip(),
            "meal_time": effective_time.isoformat(),
            **summary_fields(resolutions, dropped),
            "ingredients": result_ingredients,
            "next_step": next_step(resolutions, tool="log_meal"),
            "has_photo": photo.filename is not None,
            "photo_sha256": hash_tag,
            "deduplicated": False,
        }

    @server.tool(description=_ATTACH_MEAL_PHOTO_DESCRIPTION)
    @instrument_tool("attach_meal_photo")
    async def attach_meal_photo(
        photo_id: int,
        photo_base64: Optional[str] = None,
        source_photo_id: Optional[int] = None,
        replace: bool = False,
        ctx: Context = None,
    ) -> dict[str, Any]:
        if (photo_base64 is None) == (source_photo_id is None):
            raise ValidationError("pass exactly one of photo_base64 or source_photo_id")
        if source_photo_id is not None and source_photo_id == photo_id:
            raise ValidationError("source_photo_id must be a different photo")
        raw: Optional[bytes] = decode_photo_b64(photo_base64) if photo_base64 is not None else None
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            photo = await PhotoCRUD(db).get_by_id_owned(photo_id)
            if photo is None or photo.meal is None:
                raise NotFoundError(f"Meal photo {photo_id} not found")
            if source_photo_id is not None:
                src = await PhotoCRUD(db).get_by_id_owned(source_photo_id)
                if src is None:
                    raise NotFoundError(f"Meal photo {source_photo_id} not found")
                raw = await copy_photo_bytes(src, user_id)
            if raw is None:
                raise ValidationError("pass exactly one of photo_base64 or source_photo_id")
            hash_tag = photo_hash_tag(raw)
            if _image_hash_matches(photo, hash_tag):
                return {
                    "photo_id": photo.id,
                    "meal_id": photo.meal_id,
                    "has_photo": photo.filename is not None,
                    "photo_sha256": hash_tag,
                    "replaced": False,
                }
            if photo.filename and not replace:
                raise ValidationError("meal already has a photo; pass replace=true to overwrite")

            old_filename = photo.filename
            sole = await placement_count(db, photo.meal_id) == 1
            saved: list[str] = []
            try:
                async with unit_of_work(db):
                    saved = await store_photo_for(
                        db,
                        photo.entry,
                        photo,
                        photo.meal,
                        raw,
                        user_id,
                        bind_meal=sole,
                    )
            except Exception:
                await delete_photo_files(saved, user_id)
                raise

            replaced = bool(old_filename) and old_filename != photo.filename
            if (
                replaced
                and old_filename is not None
                and not await filename_in_use(db, old_filename)
            ):
                await delete_photo_files([old_filename, thumb_filename(old_filename)], user_id)
            return {
                "photo_id": photo.id,
                "meal_id": photo.meal_id,
                "has_photo": photo.filename is not None,
                "photo_sha256": hash_tag,
                "replaced": replaced,
            }

    @server.tool(description=_EDIT_MEAL_DESCRIPTION)
    @instrument_tool("edit_meal")
    async def edit_meal(
        photo_id: int,
        name: Optional[str] = None,
        meal_time: Optional[str] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
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

    @server.tool(description=_SET_INGREDIENTS_DESCRIPTION)
    @instrument_tool("set_ingredients")
    async def set_ingredients(
        photo_id: int,
        ingredients: list[str],
        ctx: Context = None,
    ) -> dict[str, Any]:
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            analysis = await PhotoAnalysisCRUD(db).get_for_photo_with_ingredients(photo_id)
            if analysis is None:
                raise NotFoundError("No meal analysis for this photo")
            resolutions, dropped = await resolve_for_current_user(db, ingredients)
            # One transaction: delete the old list and insert the new one, or change nothing.
            async with unit_of_work(db):
                for existing in list(analysis.ingredients):
                    await db.delete(existing)
                rows = stage_ingredient_rows(
                    db.add, resolutions, user_id=current_user_id(), analysis_id=analysis.id
                )
                await db.flush()
            created = [
                ingredient_payload(row, resolution) for row, resolution in zip(rows, resolutions)
            ]
            return {
                "photo_id": photo_id,
                **summary_fields(resolutions, dropped),
                "ingredients": created,
                "next_step": next_step(resolutions, tool="set_ingredients"),
            }

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
