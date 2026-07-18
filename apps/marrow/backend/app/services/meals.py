from __future__ import annotations

import asyncio
import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.meals import MealCRUD
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from f0rge_core.exceptions import NotFoundError, ValidationError
from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.meal import RecentMealResponse
from app.schemas.photo import PhotoResponse
from app.services.diet_flags import compute_signal_from_analyses
from app.services.entries import _photo_response, get_or_create_entry
from app.services.photo_storage import delete_photo, photo_exists, read_photo, save_photo
from app.services.photos import next_photo_filename
from f0rge_db.tenant import current_user_id


class MealService:
    """Re-log a previously-analyzed meal without re-shooting or re-running the AI.

    ``clone`` copies a confirmed meal onto a target day as a **new** canonical
    meal (decoupled from the source), with analysis pre-``confirmed``.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.photo_crud = PhotoCRUD(db)
        self.meal_crud = MealCRUD(db)
        self.analysis_crud = PhotoAnalysisCRUD(db)
        self.ingredient_crud = PhotoIngredientCRUD(db)

    async def list_recent(self, limit: int = 12) -> list[RecentMealResponse]:
        """Distinct recently-logged meals, most-recent first, deduped by dish name."""
        rows = await self.analysis_crud.list_confirmed_with_entry_dates()

        dates_per_dish: dict[str, set[datetime.date]] = {}
        for analysis, entry_date, _photo_id in rows:
            dates_per_dish.setdefault(analysis.dish_name, set()).add(entry_date)

        seen: set[str] = set()
        out: list[RecentMealResponse] = []
        for analysis, entry_date, photo_id in rows:
            dish = analysis.dish_name
            if dish in seen:
                continue
            seen.add(dish)
            signal = compute_signal_from_analyses([analysis])
            out.append(
                RecentMealResponse(
                    dish_name=dish,
                    source_photo_id=photo_id,
                    times_logged=len(dates_per_dish[dish]),
                    last_logged=entry_date,
                    diet_flags=sorted(signal.flags),
                )
            )
            if len(out) >= limit:
                break
        return out

    async def clone(
        self,
        target_date: datetime.date,
        source_photo_id: int,
        meal_time: Optional[datetime.datetime] = None,
    ) -> PhotoResponse:
        """Copy a confirmed source meal onto ``target_date`` as new, decoupled rows."""
        src_photo = await self.photo_crud.get_by_id_owned(source_photo_id)
        if src_photo is None:
            raise NotFoundError(f"No photo for analysis on photo {source_photo_id}")

        src = await self.analysis_crud.get_for_photo_with_ingredients(source_photo_id)
        if src is None:
            raise NotFoundError(f"No analysis for photo {source_photo_id}")
        if src.status != "confirmed":
            raise ValidationError("Source meal is not confirmed")
        user_id = current_user_id()
        user_id_str = str(user_id)
        if not photo_exists(src_photo.filename, user_id=user_id_str):
            raise NotFoundError("Source photo file is missing on disk")

        src_bytes = await asyncio.to_thread(read_photo, src_photo.filename, user_id=user_id_str)

        entry = await get_or_create_entry(self.db, target_date)
        new_filename = await next_photo_filename(self.db, entry)
        now = datetime.datetime.utcnow()
        effective_meal_time = meal_time if meal_time is not None else now

        meal = Meal(
            owner_user_id=user_id,
            filename=new_filename,
            label=src_photo.label,
            original_filename=src_photo.original_filename,
            meal_time=effective_meal_time,
            created_at=now,
        )
        await self.meal_crud.add_and_flush(meal)

        new_photo = Photo(
            user_id=user_id,
            entry_id=entry.id,
            meal_id=meal.id,
            filename=new_filename,
            label=src_photo.label,
            original_filename=src_photo.original_filename,
            meal_time=effective_meal_time,
            created_at=now,
        )
        await self.photo_crud.add_and_flush(new_photo)

        new_analysis = PhotoAnalysis(
            user_id=user_id,
            meal_id=meal.id,
            photo_id=new_photo.id,
            status="confirmed",
            dish_name=src.dish_name,
            cuisine=src.cuisine,
            dish_confidence=src.dish_confidence,
            model_id=src.model_id,
            raw_response=src.raw_response,
            gluten_free_confirmed=src.gluten_free_confirmed,
            lactose_free_confirmed=src.lactose_free_confirmed,
        )
        await self.analysis_crud.add_and_flush(new_analysis)

        for si in src.ingredients:
            self.ingredient_crud.add(
                PhotoIngredient(
                    user_id=user_id,
                    analysis_id=new_analysis.id,
                    name=si.name,
                    canonical_name=si.canonical_name,
                    visible=si.visible,
                    confidence=si.confidence,
                    user_edited=si.user_edited,
                    histamine_score=si.histamine_score,
                    fodmap_oligos=si.fodmap_oligos,
                    fodmap_fructose=si.fodmap_fructose,
                    fodmap_polyols=si.fodmap_polyols,
                    fodmap_lactose=si.fodmap_lactose,
                    contains_gluten=si.contains_gluten,
                    contains_dairy=si.contains_dairy,
                )
            )

        await asyncio.to_thread(save_photo, src_bytes, new_filename, user_id=user_id_str)

        try:
            new_photo = await self.photo_crud.commit_refresh(new_photo)
        except Exception:
            await asyncio.to_thread(delete_photo, new_filename, user_id=user_id_str)
            raise
        # Serialize via _photo_response: raw ORM return would make the response
        # model touch the unloaded diet_tags relationship (MissingGreenlet).
        return _photo_response(new_photo)
