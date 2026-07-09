from __future__ import annotations

import asyncio
import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.meal import RecentMealResponse
from app.services.diet_flags import compute_signal_from_analyses
from app.services.entries import get_or_create_entry
from app.services.photo_storage import delete_photo, photo_exists, read_photo, save_photo
from app.services.photos import next_photo_filename


class MealService:
    """Re-log a previously-analyzed meal without re-shooting or re-running the AI.

    A "meal" is one Photo + its confirmed PhotoAnalysis + that analysis's
    PhotoIngredient rows. ``clone`` copies those onto a target day as brand-new
    rows (decoupled from the source), with the analysis pre-``confirmed`` so it
    counts toward the diet signal immediately. The vision AI is never invoked.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_recent(self, limit: int = 12) -> list[RecentMealResponse]:
        """Distinct recently-logged meals, most-recent first, deduped by dish name."""
        stmt = (
            select(PhotoAnalysis, Entry.date)
            .join(Photo, PhotoAnalysis.photo_id == Photo.id)
            .join(Entry, Photo.entry_id == Entry.id)
            # selectinload is mandatory: compute_signal_from_analyses walks
            # analysis.ingredients, and a lazy load here would raise MissingGreenlet.
            .options(selectinload(PhotoAnalysis.ingredients))
            .where(
                PhotoAnalysis.status == "confirmed",
                PhotoAnalysis.dish_name.isnot(None),
            )
            .order_by(Entry.date.desc(), PhotoAnalysis.photo_id.desc())
        )
        rows = (await self.db.execute(stmt)).all()

        # times_logged counts DISTINCT dates a dish appears on, so two photos of
        # the same dish on one day count once.
        dates_per_dish: dict[str, set[datetime.date]] = {}
        for analysis, entry_date in rows:
            dates_per_dish.setdefault(analysis.dish_name, set()).add(entry_date)

        # Rows are date-desc, so the first occurrence of each dish is its
        # most-recent instance = the representative we offer for cloning.
        seen: set[str] = set()
        out: list[RecentMealResponse] = []
        for analysis, entry_date in rows:
            dish = analysis.dish_name
            if dish in seen:
                continue
            seen.add(dish)
            signal = compute_signal_from_analyses([analysis])
            out.append(
                RecentMealResponse(
                    dish_name=dish,
                    source_photo_id=analysis.photo_id,
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
        meal_time: datetime.datetime | None = None,
    ) -> Photo:
        """Copy a confirmed source meal onto ``target_date`` as new, decoupled rows."""
        # 1. Load + validate the source before writing anything.
        src = (
            await self.db.execute(
                select(PhotoAnalysis)
                .options(
                    selectinload(PhotoAnalysis.ingredients),
                    selectinload(PhotoAnalysis.photo),
                )
                .where(PhotoAnalysis.photo_id == source_photo_id)
            )
        ).scalar_one_or_none()
        if src is None:
            raise NotFoundError(f"No analysis for photo {source_photo_id}")
        if src.status != "confirmed":
            raise ValidationError("Source meal is not confirmed")
        src_photo = src.photo
        if not photo_exists(src_photo.filename):
            raise NotFoundError("Source photo file is missing on disk")

        src_bytes = await asyncio.to_thread(read_photo, src_photo.filename)

        # 2. Target entry (get-or-create, flush-only) + a fresh filename.
        entry = await get_or_create_entry(self.db, target_date)
        new_filename = await next_photo_filename(self.db, entry)
        now = datetime.datetime.utcnow()

        # 3. Stage all rows; a single commit below keeps photo + analysis +
        #    ingredients atomic.
        new_photo = Photo(
            entry_id=entry.id,
            filename=new_filename,
            label=src_photo.label,
            original_filename=src_photo.original_filename,
            meal_time=meal_time if meal_time is not None else now,
            created_at=now,
        )
        self.db.add(new_photo)
        await self.db.flush()

        new_analysis = PhotoAnalysis(
            photo_id=new_photo.id,
            status="confirmed",  # skip pending/analyzing — counts toward the signal now
            dish_name=src.dish_name,
            cuisine=src.cuisine,
            dish_confidence=src.dish_confidence,
            model_id=src.model_id,
            raw_response=src.raw_response,
        )
        self.db.add(new_analysis)
        await self.db.flush()

        for si in src.ingredients:
            self.db.add(
                PhotoIngredient(
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

        # 4. Copy the image file BEFORE commit — mirrors upload's invariant that a
        #    file on disk implies a committed row. No resize: the source on disk is
        #    already a processed JPEG.
        await asyncio.to_thread(save_photo, src_bytes, new_filename)

        # 5. Commit; on failure remove the just-copied file so the next filename
        #    scan doesn't collide with an orphan (mirrors upload's cleanup).
        try:
            await self.db.commit()
        except Exception:
            await asyncio.to_thread(delete_photo, new_filename)
            raise
        await self.db.refresh(new_photo)
        return new_photo
