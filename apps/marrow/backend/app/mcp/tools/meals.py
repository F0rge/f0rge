from __future__ import annotations

import asyncio
import base64
import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import Context, FastMCP
from app.cache.invalidation import invalidate_user_insights_cache
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
from app.services.photo_storage import resize_image, save_photo, thumb_filename
from app.prompts.ingredient_rules import INGREDIENT_TOOL_NOTE
from app.services.photos import entry_photo_upload_lock, next_photo_filename
from app.crud.base import unit_of_work
from app.config import settings
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.tenant import apply_session_user_id, current_user_id


async def _tags_for_photo(db, photo_id: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tag in await MealTagCRUD(db).list_for_source_photo(photo_id):
        user = await MealTagService(db).social_crud.get_by_id(tag.tagged_user_id)
        handle = user.handle if user is not None else ""
        items.append({"handle": handle, "status": tag.status})
    return items


async def _move_tag_copies(
    db,
    source_photo_id: int,
    tagger_id,
    new_date: datetime.date,
    meal_time: Optional[datetime.datetime],
) -> list[tuple[Any, datetime.date]]:
    """Follow a source meal that moved day: retarget its tags and delivered copies.

    Same tenant-switch pattern as ``TagDeliveryService._deliver_tag``: tags are read and
    updated as the tagger, each recipient's placement is moved under the recipient's own
    RLS context (their entry for ``new_date`` is created if missing), then the session
    returns to the tagger. Pending tags only get ``source_date``, so a later delivery
    lands on the new day. Returns ``(recipient_id, old_date)`` per moved copy.
    """
    tags = await MealTagCRUD(db).list_for_source_photo(source_photo_id)
    delivered: list[tuple[Any, int]] = []
    for tag in tags:
        tag.source_date = new_date
        if tag.status == "delivered" and tag.delivered_photo_id is not None:
            delivered.append((tag.tagged_user_id, tag.delivered_photo_id))
    await db.flush()
    moved: list[tuple[Any, datetime.date]] = []
    try:
        for recipient_id, copy_id in delivered:
            await apply_session_user_id(db, recipient_id)
            copy = await PhotoCRUD(db).get_by_id_owned(copy_id)
            if copy is None or copy.source_photo_id != source_photo_id:
                continue
            old_date = copy.entry.date
            if old_date != new_date:
                copy.entry = await get_or_create_entry(db, new_date)
            if meal_time is not None:
                copy.meal_time = meal_time
            await db.flush()
            moved.append((recipient_id, old_date))
    finally:
        await apply_session_user_id(db, tagger_id)
    return moved


def _local_tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def _to_utc_naive(value: datetime.datetime) -> datetime.datetime:
    """Store meal times like the app does: naive UTC.

    A naive value is wall-clock time in ``settings.app_timezone`` (Europe/Luxembourg);
    a value with an explicit offset is kept as that instant.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=_local_tz())
    return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def _local_date(value: datetime.datetime) -> datetime.date:
    """Calendar day of ``value`` in the app timezone (naive = already local)."""
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(_local_tz()).date()


def _time_fields(stored_utc: Optional[datetime.datetime]) -> dict[str, Any]:
    if stored_utc is None:
        return {"meal_time": None, "meal_time_local": None}
    aware = stored_utc.replace(tzinfo=datetime.timezone.utc)
    return {
        "meal_time": aware.isoformat(),
        "meal_time_local": aware.astimezone(_local_tz()).isoformat(),
    }


_TIME_NOTE = (
    "meal_time without an offset (HH:MM or a naive ISO datetime) is local time in "
    "Europe/Luxembourg; an ISO datetime with an explicit offset is kept as that instant. "
    "Stored in UTC; the response gives meal_time (UTC) and meal_time_local. "
)


_LOG_MEAL_DESCRIPTION = (
    "Log a meal on a day. Returns when the meal row exists (no background vision). "
    "`name` is the meal/product name and may carry brand, pack size and quantity. "
    + _TIME_NOTE
    + INGREDIENT_TOOL_NOTE
)
_SET_INGREDIENTS_DESCRIPTION = (
    "Replace the whole ingredient list on an existing meal (confirmed analysis). "
    + INGREDIENT_TOOL_NOTE
)
_EDIT_MEAL_DESCRIPTION = (
    _TIME_NOTE
    + "Update a meal's display name and/or meal time. A meal_time on another calendar day "
    "moves the meal (and the copies delivered to people tagged on it) to that day, creating "
    "the day if it has no check-in yet; the day is meal_time's local Europe/Luxembourg date. "
    "Does not change ingredients: "
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
        ctx: Context = None,
    ) -> dict[str, Any]:
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

        if meal_time:
            effective_time = _to_utc_naive(effective_time)

        async with mcp_tools.scoped_main_session(user_id) as db:
            # Resolve (and validate) before any write so a bad request creates no meal.
            resolutions, dropped = await resolve_for_current_user(db, ingredients or [])
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

            result_ingredients = [
                ingredient_payload(row, resolution) for row, resolution in zip(rows, resolutions)
            ]
            # The API caches GET /entries/{date}; without this the app keeps serving
            # the day without the new meal (and its diet flags) until the TTL expires.
            await invalidate_user_insights_cache(current_user_id(), parsed)

        return {
            "photo_id": photo.id,
            "meal_id": meal.id,
            "date": str(parsed),
            "name": name.strip(),
            **_time_fields(effective_time),
            **summary_fields(resolutions, dropped),
            "ingredients": result_ingredients,
            "next_step": next_step(resolutions, tool="log_meal"),
            "has_photo": photo.filename is not None,
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
            old_date = photo.entry.date
            new_date = old_date
            if meal_time is not None:
                try:
                    parsed_time = datetime.datetime.fromisoformat(meal_time)
                except ValueError as exc:
                    raise ValidationError("meal_time must be ISO datetime") from exc
                # Day = local calendar date of the given time (naive input is local).
                new_date = _local_date(parsed_time)
                parsed_time = _to_utc_naive(parsed_time)
                photo.meal_time = parsed_time
                if photo.meal is not None:
                    photo.meal.meal_time = parsed_time
                if new_date != old_date:
                    # Day membership is Photo.entry_id, not meal_time: re-home the
                    # placement or the meal stays on the old day with a new time.
                    photo.entry = await get_or_create_entry(db, new_date)
            moved_copies: list[tuple[Any, datetime.date]] = []
            if new_date != old_date:
                moved_copies = await _move_tag_copies(
                    db, photo_id, current_user_id(), new_date, photo.meal_time
                )
            await PhotoCRUD(db).commit_refresh(photo)
            await invalidate_user_insights_cache(current_user_id(), old_date)
            if new_date != old_date:
                await invalidate_user_insights_cache(current_user_id(), new_date)
            for recipient_id, recipient_old_date in moved_copies:
                await invalidate_user_insights_cache(recipient_id, recipient_old_date)
                await invalidate_user_insights_cache(recipient_id, new_date)
            return {
                "photo_id": photo.id,
                "date": str(new_date),
                "name": photo.label,
                **_time_fields(photo.meal_time),
                "moved_tag_copies": len(moved_copies),
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
            photo = await PhotoCRUD(db).get_by_id_owned(photo_id)
            if photo is not None:
                await invalidate_user_insights_cache(current_user_id(), photo.entry.date)
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
            entry_date = photo.entry.date
            for tag in await tag_service.crud.list_for_source_photo(photo_id):
                if tag.status in ("pending_analysis", "pending_approval"):
                    await tag_service.cancel(tag.id)
            if handles:
                await tag_service.add_tags_to_photo(photo_id, handles)
            tags = await _tags_for_photo(db, photo_id)
            await invalidate_user_insights_cache(current_user_id(), entry_date)
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
