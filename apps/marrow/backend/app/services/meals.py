from __future__ import annotations

import asyncio
import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.meals import MealCRUD
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from app.crud.platform_meals import PlatformMealCRUD
from app.cache.invalidation import invalidate_user_insights_cache
from f0rge_core.exceptions import NotFoundError, ValidationError
from app.models.dietary_ingredient import DietaryIngredient
from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.meal import PlatformMealResponse, RecentMealResponse
from app.schemas.photo import PhotoResponse
from app.services.diet_flags import compute_signal_from_analyses, flags_from_dietary_ingredients
from app.services.entries import _photo_response, get_or_create_entry
from app.services.ingredient_lookup import IngredientLookupService
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
        self.platform_crud = PlatformMealCRUD(db)
        self.lookup = IngredientLookupService(db)

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

    async def list_library(
        self,
        *,
        q: Optional[str] = None,
        cuisine: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[PlatformMealResponse]:
        # Cap unfiltered browse so diet-flag resolution stays under gateway
        # timeouts; searches keep a higher ceiling so matches aren't truncated.
        if limit is None:
            effective_limit = 100 if (q or cuisine) else 60
        else:
            effective_limit = limit
        meals = await self.platform_crud.list_active(q=q, cuisine=cuisine, limit=effective_limit)
        # Deduped cache — repeated ingredients across meals (rice, chicken, …)
        # were previously N+1 lookups and timed out the library endpoint.
        lookup_cache: dict[str, Optional[DietaryIngredient]] = {}
        out: list[PlatformMealResponse] = []
        for meal in meals:
            dietary_items: list[DietaryIngredient] = []
            for ingredient in meal.ingredients:
                name = ingredient.canonical_name
                if name not in lookup_cache:
                    lookup_cache[name] = await self.lookup.lookup(name)
                match = lookup_cache[name]
                if match is not None:
                    dietary_items.append(match)
            out.append(
                PlatformMealResponse(
                    id=meal.id,
                    slug=meal.slug,
                    name=meal.name,
                    cuisine=meal.cuisine,
                    icon_key=meal.icon_key,
                    ingredients=[ing.canonical_name for ing in meal.ingredients],
                    diet_flags=flags_from_dietary_ingredients(dietary_items),
                )
            )
        return out

    async def list_library_cuisines(self) -> list[str]:
        return await self.platform_crud.list_cuisines()

    async def log_from_library(
        self,
        target_date: datetime.date,
        platform_meal_id: int,
        meal_time: Optional[datetime.datetime] = None,
    ) -> PhotoResponse:
        platform = await self.platform_crud.get_by_id(platform_meal_id)
        if platform is None:
            raise NotFoundError(f"Platform meal {platform_meal_id} not found")

        user_id = current_user_id()
        entry = await get_or_create_entry(self.db, target_date)
        now = datetime.datetime.utcnow()
        effective_meal_time = meal_time if meal_time is not None else now

        meal = Meal(
            owner_user_id=user_id,
            filename=None,
            icon_key=platform.icon_key,
            platform_meal_id=platform.id,
            label=None,
            meal_time=effective_meal_time,
            created_at=now,
        )
        await self.meal_crud.add_and_flush(meal)

        photo = Photo(
            user_id=user_id,
            entry_id=entry.id,
            meal_id=meal.id,
            filename=None,
            label=None,
            meal_time=effective_meal_time,
            created_at=now,
        )
        await self.photo_crud.add_and_flush(photo)

        analysis = PhotoAnalysis(
            user_id=user_id,
            meal_id=meal.id,
            photo_id=photo.id,
            status="confirmed",
            dish_name=platform.name,
            cuisine=platform.cuisine,
            dish_confidence=1.0,
        )
        await self.analysis_crud.add_and_flush(analysis)

        for ingredient in platform.ingredients:
            match = await self.lookup.lookup(ingredient.canonical_name)
            self.ingredient_crud.add(
                PhotoIngredient(
                    user_id=user_id,
                    analysis_id=analysis.id,
                    name=ingredient.canonical_name,
                    canonical_name=match.canonical_name if match else None,
                    visible=True,
                    confidence=1.0,
                    user_edited=False,
                    histamine_score=match.histamine_score if match else None,
                    fodmap_oligos=match.fodmap_oligos if match else None,
                    fodmap_fructose=match.fodmap_fructose if match else None,
                    fodmap_polyols=match.fodmap_polyols if match else None,
                    fodmap_lactose=match.fodmap_lactose if match else None,
                    contains_gluten=match.contains_gluten if match else None,
                    contains_dairy=match.contains_dairy if match else None,
                )
            )

        await self.photo_crud.save()
        await invalidate_user_insights_cache(user_id, target_date)
        photo.meal = meal
        return _photo_response(photo)

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

        src_meal = src_photo.meal
        icon_only = src_photo.filename is None
        if icon_only:
            if src_meal is None or not src_meal.icon_key:
                raise ValidationError("Source meal has no image or icon")
            new_filename = None
            icon_key = src_meal.icon_key
            platform_meal_id = src_meal.platform_meal_id
            src_bytes = None
        else:
            if not photo_exists(src_photo.filename, user_id=user_id_str):
                raise NotFoundError("Source photo file is missing on disk")
            src_bytes = await asyncio.to_thread(read_photo, src_photo.filename, user_id=user_id_str)
            new_filename = None
            icon_key = None
            platform_meal_id = None

        entry = await get_or_create_entry(self.db, target_date)
        now = datetime.datetime.utcnow()
        effective_meal_time = meal_time if meal_time is not None else now

        if not icon_only:
            new_filename = await next_photo_filename(self.db, entry)

        meal = Meal(
            owner_user_id=user_id,
            filename=new_filename,
            icon_key=icon_key,
            platform_meal_id=platform_meal_id,
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

        if src_bytes is not None and new_filename is not None:
            await asyncio.to_thread(save_photo, src_bytes, new_filename, user_id=user_id_str)

        try:
            # save(), not commit_refresh(): refresh expires .analysis/.diet_tags,
            # and _photo_response's unloaded-guard then triggers lazy IO
            # (MissingGreenlet). A fresh clone has no diet tags either way.
            await self.photo_crud.save()
        except Exception:
            if new_filename is not None:
                await asyncio.to_thread(delete_photo, new_filename, user_id=user_id_str)
            raise
        # Mirror PhotoService.upload — otherwise GET /entries/{date} can keep
        # serving a Redis-cached entry missing the clone for up to TTL (300s).
        await invalidate_user_insights_cache(user_id, target_date)
        if icon_only:
            new_photo.meal = meal
        # Serialize via _photo_response: raw ORM return would make the response
        # model touch the unloaded diet_tags relationship (MissingGreenlet).
        return _photo_response(new_photo)
