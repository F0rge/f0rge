from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_maker
from app.exceptions import NotFoundError
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.food_analysis import IngredientCreate, IngredientUpdate
from app.services.ingredient_lookup import IngredientLookupService
from app.services.obsidian_prefetch import render_and_write_daily_file
from app.services.vision_prompt import build_messages, parse_vision_response

logger = logging.getLogger(__name__)


class FoodAnalysisService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_analysis(self, photo_id: int) -> Optional[PhotoAnalysis]:
        """Get analysis for a photo, with eagerly loaded ingredients."""
        return (
            await self.db.execute(
                select(PhotoAnalysis)
                .options(selectinload(PhotoAnalysis.ingredients))
                .where(PhotoAnalysis.photo_id == photo_id)
            )
        ).scalar_one_or_none()

    async def confirm_analysis(self, analysis_id: int) -> PhotoAnalysis:
        """Set analysis status to confirmed and re-render vault."""
        analysis = (
            await self.db.execute(
                select(PhotoAnalysis)
                .options(selectinload(PhotoAnalysis.ingredients))
                .where(PhotoAnalysis.id == analysis_id)
            )
        ).scalar_one_or_none()
        if not analysis:
            raise NotFoundError("Analysis not found")
        analysis.status = "confirmed"
        await self.db.commit()
        await self.db.refresh(analysis)
        await self._rerender_vault(analysis.photo_id)
        return analysis

    async def update_ingredient(
        self, ingredient_id: int, updates: IngredientUpdate
    ) -> PhotoIngredient:
        """Update an ingredient and set user_edited flag."""
        ingredient = (
            await self.db.execute(
                select(PhotoIngredient).where(PhotoIngredient.id == ingredient_id)
            )
        ).scalar_one_or_none()
        if not ingredient:
            raise NotFoundError("Ingredient not found")

        update_data = updates.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(ingredient, key, value)
        ingredient.user_edited = True

        # If name changed and no canonical_name override, re-lookup
        if "name" in update_data and "canonical_name" not in update_data:
            lookup = IngredientLookupService(self.db)
            match = await lookup.lookup(ingredient.name)
            if match:
                ingredient.canonical_name = match.canonical_name
                ingredient.histamine_score = match.histamine_score
                ingredient.fodmap_oligos = match.fodmap_oligos
                ingredient.fodmap_fructose = match.fodmap_fructose
                ingredient.fodmap_polyols = match.fodmap_polyols
                ingredient.fodmap_lactose = match.fodmap_lactose
                ingredient.contains_gluten = match.contains_gluten
                ingredient.contains_dairy = match.contains_dairy

        await self.db.commit()
        await self.db.refresh(ingredient)
        return ingredient

    async def add_ingredient(self, analysis_id: int, data: IngredientCreate) -> PhotoIngredient:
        """Add a manually-entered ingredient to an analysis."""
        analysis = (
            await self.db.execute(select(PhotoAnalysis).where(PhotoAnalysis.id == analysis_id))
        ).scalar_one_or_none()
        if not analysis:
            raise NotFoundError("Analysis not found")

        lookup = IngredientLookupService(self.db)
        match = await lookup.lookup(data.name)

        ingredient = PhotoIngredient(
            analysis_id=analysis_id,
            name=data.name,
            canonical_name=match.canonical_name if match else data.canonical_name,
            visible=data.visible,
            confidence=data.confidence,
            user_edited=True,
            histamine_score=match.histamine_score if match else None,
            fodmap_oligos=match.fodmap_oligos if match else None,
            fodmap_fructose=match.fodmap_fructose if match else None,
            fodmap_polyols=match.fodmap_polyols if match else None,
            fodmap_lactose=match.fodmap_lactose if match else None,
            contains_gluten=match.contains_gluten if match else None,
            contains_dairy=match.contains_dairy if match else None,
        )
        self.db.add(ingredient)
        await self.db.commit()
        await self.db.refresh(ingredient)
        return ingredient

    async def delete_analysis(self, analysis_id: int) -> None:
        """Delete an analysis and its ingredients (cascade)."""
        analysis = (
            await self.db.execute(select(PhotoAnalysis).where(PhotoAnalysis.id == analysis_id))
        ).scalar_one_or_none()
        if analysis:
            await self.db.delete(analysis)
            await self.db.commit()

    async def create_pending_analysis(self, photo_id: int) -> PhotoAnalysis:
        """Create a new pending analysis record for a photo."""
        analysis = PhotoAnalysis(
            photo_id=photo_id,
            status="pending",
            model_id=settings.openrouter_model,
        )
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def delete_ingredient(self, ingredient_id: int) -> None:
        """Delete an ingredient by id."""
        ingredient = (
            await self.db.execute(
                select(PhotoIngredient).where(PhotoIngredient.id == ingredient_id)
            )
        ).scalar_one_or_none()
        if not ingredient:
            raise NotFoundError("Ingredient not found")
        await self.db.delete(ingredient)
        await self.db.commit()

    async def get_analysis_or_404(self, photo_id: int) -> PhotoAnalysis:
        """Get analysis for a photo; raise NotFoundError if absent."""
        analysis = await self.get_analysis(photo_id)
        if analysis is None:
            raise NotFoundError("No analysis found for this photo")
        return analysis

    async def retry_analysis(
        self, photo_id: int, background_tasks: BackgroundTasks
    ) -> PhotoAnalysis:
        existing = await self.get_analysis(photo_id)
        if existing:
            await self.delete_analysis(existing.id)
        new_analysis = await self.create_pending_analysis(photo_id)
        background_tasks.add_task(trigger_analysis_background, photo_id)
        return new_analysis

    async def add_ingredient_to_photo(
        self, photo_id: int, data: IngredientCreate
    ) -> PhotoIngredient:
        """Add ingredient to the analysis for the given photo; raises NotFoundError if no analysis."""
        analysis = await self.get_analysis(photo_id)
        if analysis is None:
            raise NotFoundError("No analysis found for this photo")
        return await self.add_ingredient(analysis.id, data)

    async def _rerender_vault(self, photo_id: int) -> None:
        """Re-render the Obsidian vault file for the entry owning this photo."""
        photo = (
            await self.db.execute(select(Photo).where(Photo.id == photo_id))
        ).scalar_one_or_none()
        if photo and photo.entry:
            entry = photo.entry
            await self.db.refresh(entry)
            await render_and_write_daily_file(self.db, entry, entry.photos)


# ---------------------------------------------------------------------------
# Background trigger (runs outside request lifecycle)
# ---------------------------------------------------------------------------


async def trigger_analysis_background(photo_id: int) -> None:
    """Run food photo analysis in a background task.

    Opens its own DB session because FastAPI BackgroundTasks execute
    after the response is sent and the request session is closed.
    """
    analysis: Optional[PhotoAnalysis] = None
    try:
        async with async_session_maker() as db:
            # Guard: without an API key we cannot call OpenRouter.
            if not settings.openrouter_api_key:
                logger.warning(
                    "Food analysis skipped for photo %d: OPENROUTER_API_KEY not "
                    "configured. Set the env var or disable the feature with "
                    "FOOD_ANALYSIS_ENABLED=false.",
                    photo_id,
                )
                existing = (
                    await db.execute(
                        select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
                    )
                ).scalar_one_or_none()
                if existing is None:
                    analysis = PhotoAnalysis(
                        photo_id=photo_id,
                        status="failed",
                        model_id=settings.openrouter_model,
                        error_message="OPENROUTER_API_KEY not configured",
                    )
                    db.add(analysis)
                else:
                    existing.status = "failed"
                    existing.error_message = "OPENROUTER_API_KEY not configured"
                await db.commit()
                return

            # Reuse a pending record or skip if already running/finished.
            existing = (
                await db.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id))
            ).scalar_one_or_none()

            if existing and existing.status not in ("pending", "failed"):
                logger.info(
                    "Analysis already exists for photo %d (status=%s), skipping",
                    photo_id,
                    existing.status,
                )
                return

            if existing:
                analysis = existing
                analysis.status = "analyzing"
                analysis.error_message = None
                analysis.model_id = settings.openrouter_model
            else:
                analysis = PhotoAnalysis(
                    photo_id=photo_id,
                    status="analyzing",
                    model_id=settings.openrouter_model,
                )
                db.add(analysis)
            await db.commit()
            await db.refresh(analysis)

            # Read photo file from disk (blocking I/O wrapped in thread)
            photo = (
                await db.execute(select(Photo).where(Photo.id == photo_id))
            ).scalar_one_or_none()
            if not photo:
                raise ValueError(f"Photo {photo_id} not found in database")

            photo_path = os.path.join(settings.photo_dir, photo.filename)
            if not os.path.exists(photo_path):
                raise FileNotFoundError(f"Photo file not found: {photo_path}")

            image_bytes = await asyncio.to_thread(Path(photo_path).read_bytes)

            messages = build_messages(image_bytes)

            from app.services.llm.factory import resolve_llm_credentials
            from app.services.llm.openrouter import OpenRouterClient

            api_key, model = await resolve_llm_credentials(db)
            llm_client = OpenRouterClient(api_key=api_key or "", default_model=model)

            raw_content = await llm_client.complete_with_image(messages)
            analysis.raw_response = raw_content

            vision_result = parse_vision_response(raw_content)

            analysis.dish_name = vision_result.dish_name
            analysis.cuisine = vision_result.cuisine
            analysis.dish_confidence = vision_result.confidence

            lookup = IngredientLookupService(db)
            for vi in vision_result.ingredients:
                match = await lookup.lookup(vi.name)
                ingredient = PhotoIngredient(
                    analysis_id=analysis.id,
                    name=vi.name,
                    canonical_name=match.canonical_name if match else None,
                    visible=vi.visible,
                    confidence=vi.confidence,
                    user_edited=False,
                    histamine_score=match.histamine_score if match else None,
                    fodmap_oligos=match.fodmap_oligos if match else None,
                    fodmap_fructose=match.fodmap_fructose if match else None,
                    fodmap_polyols=match.fodmap_polyols if match else None,
                    fodmap_lactose=match.fodmap_lactose if match else None,
                    contains_gluten=match.contains_gluten if match else None,
                    contains_dairy=match.contains_dairy if match else None,
                )
                db.add(ingredient)

            analysis.status = "complete"
            await db.commit()

            # Re-render Obsidian vault file
            photo = (
                await db.execute(select(Photo).where(Photo.id == photo_id))
            ).scalar_one_or_none()
            if photo and photo.entry:
                entry = photo.entry
                await db.refresh(entry)
                await render_and_write_daily_file(db, entry, entry.photos)

            logger.info(
                "Analysis complete for photo %d: %s (%d ingredients)",
                photo_id,
                vision_result.dish_name,
                len(vision_result.ingredients),
            )

    except Exception as e:
        logger.exception("Food analysis failed for photo %d", photo_id)
        if analysis is not None:
            try:
                async with async_session_maker() as db:
                    fresh = (
                        await db.execute(
                            select(PhotoAnalysis).where(PhotoAnalysis.id == analysis.id)
                        )
                    ).scalar_one_or_none()
                    if fresh:
                        fresh.status = "failed"
                        # Full traceback is already in logs via logger.exception above.
                        # Store only a short human-readable summary so the UI doesn't
                        # display a raw multi-line stack trace.
                        fresh.error_message = f"{type(e).__name__}: {str(e)[:200]}"
                        await db.commit()
            except Exception:
                logger.exception("Failed to update analysis status for photo %d", photo_id)
