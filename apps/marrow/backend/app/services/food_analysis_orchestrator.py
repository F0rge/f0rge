from __future__ import annotations

import asyncio
import logging
import uuid
from typing import NamedTuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.invalidation import invalidate_user_insights_cache
from app.config import settings
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from app.database import async_session_maker
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.catalog_context import build_catalog_context
from app.services.food_analysis import analysis_needs_review
from app.services.ingredient_lookup import IngredientLookupService
from app.services.vision_prompt import VisionResult, build_messages, parse_vision_response
from f0rge_core.exceptions import NotFoundError
from f0rge_db.tenant import apply_session_user_id

logger = logging.getLogger(__name__)


class _PhotoContext(NamedTuple):
    """Everything the vision call and the write-back need, resolved once."""

    analysis: PhotoAnalysis
    photo: Photo
    user_id: uuid.UUID
    user_id_str: str
    model: str
    api_key: str


class _LoadContextResult(NamedTuple):
    context: Optional[_PhotoContext]
    terminal_status: Optional[str] = None


async def _fail_stuck_analysis(
    analysis_crud: PhotoAnalysisCRUD,
    *,
    meal_id: Optional[int],
    message: str,
) -> None:
    if meal_id is None:
        return
    existing = await analysis_crud.get_by_meal_id(meal_id)
    if existing and existing.status in ("pending", "analyzing"):
        existing.status = "failed"
        existing.error_message = message
        await analysis_crud.save()


async def _load_photo_context(
    db: AsyncSession,
    photo_id: int,
    user_id: Optional[uuid.UUID],
    *,
    meal_id: Optional[int] = None,
) -> _LoadContextResult:
    """Resolve owner + LLM credentials and flip the analysis row to analyzing.

    ``terminal_status`` is set when the pipeline should stop without running
    vision (missing photo, no API key, already finished).

    Airflow / inline paths always reclaim ``analyzing`` rows. The legacy
    BackgroundTasks path still skips a fresh concurrent duplicate within
    ``meal_analysis_stale_analyzing_minutes``.
    """
    analysis_crud = PhotoAnalysisCRUD(db)
    photo_crud = PhotoCRUD(db)

    if user_id is None:
        resolved = await photo_crud.get_user_id(photo_id)
        if resolved is None:
            logger.warning("Skipping analysis for missing photo %d", photo_id)
            await _fail_stuck_analysis(
                analysis_crud,
                meal_id=meal_id,
                message="Photo no longer available",
            )
            return _LoadContextResult(None, "failed")
        user_id = resolved
    user_id_str = str(user_id)
    await apply_session_user_id(db, user_id)

    photo = await photo_crud.get_by_id(photo_id)
    if not photo:
        logger.warning("Skipping analysis for missing photo %d", photo_id)
        await _fail_stuck_analysis(
            analysis_crud,
            meal_id=meal_id,
            message="Photo no longer available",
        )
        return _LoadContextResult(None, "failed")

    from app.services.llm.factory import resolve_llm_credentials

    api_key, model = await resolve_llm_credentials(db, user_id=user_id)
    if not api_key:
        logger.warning(
            "Food analysis skipped for photo %d: no LLM API key configured. "
            "Set OPENROUTER_API_KEY or add a key in Settings, or disable the "
            "feature with FOOD_ANALYSIS_ENABLED=false.",
            photo_id,
        )
        existing = await analysis_crud.get_by_meal_id(photo.meal_id)
        if existing is None:
            analysis_crud.add(
                PhotoAnalysis(
                    user_id=user_id,
                    meal_id=photo.meal_id,
                    photo_id=photo_id,
                    status="failed",
                    model_id=model,
                    error_message="LLM API key not configured",
                )
            )
        else:
            existing.status = "failed"
            existing.error_message = "LLM API key not configured"
            existing.model_id = model
        await analysis_crud.save()
        return _LoadContextResult(None, "failed")

    existing = await analysis_crud.get_by_meal_id(photo.meal_id)

    if existing and existing.status in ("confirmed", "needs_review"):
        logger.info(
            "Analysis already finished for photo %d (status=%s), skipping",
            photo_id,
            existing.status,
        )
        return _LoadContextResult(None, existing.status)

    if (
        existing
        and existing.status == "analyzing"
        and not settings.airflow_api_url
        and not settings.meal_analysis_inline
    ):
        # Legacy BackgroundTasks only: skip a fresh concurrent duplicate.
        from datetime import datetime, timedelta

        stale_after = timedelta(minutes=settings.meal_analysis_stale_analyzing_minutes)
        stamp = existing.updated_at or existing.created_at
        if stamp is not None and datetime.utcnow() - stamp.replace(tzinfo=None) < stale_after:
            logger.info(
                "Analysis already running for photo %d, skipping duplicate",
                photo_id,
            )
            return _LoadContextResult(None)

    if existing:
        analysis = existing
        analysis.status = "analyzing"
        analysis.error_message = None
        analysis.model_id = model
        if analysis.photo_id is None:
            analysis.photo_id = photo_id
    else:
        analysis = PhotoAnalysis(
            user_id=user_id,
            meal_id=photo.meal_id,
            photo_id=photo_id,
            status="analyzing",
            model_id=model,
        )
        analysis_crud.add(analysis)
    analysis = await analysis_crud.commit_refresh(analysis)

    return _LoadContextResult(
        _PhotoContext(
            analysis=analysis,
            photo=photo,
            user_id=user_id,
            user_id_str=user_id_str,
            model=model,
            api_key=api_key,
        )
    )


async def extract_vision(
    photo: Photo,
    user_id_str: str,
    api_key: str,
    model: str,
    catalog_context: str = "",
) -> tuple[str, VisionResult]:
    """Stage: read image + OpenRouter vision → structured VisionResult."""
    from app.services.photo_storage import photo_exists, read_photo

    if not photo_exists(photo.filename, user_id=user_id_str):
        raise NotFoundError(f"Photo file not found: {photo.filename}")

    image_bytes = await asyncio.to_thread(read_photo, photo.filename, user_id=user_id_str)
    messages = build_messages(image_bytes, catalog_context=catalog_context or None)

    from app.services.llm.openrouter import OpenRouterClient

    llm_client = OpenRouterClient(api_key=api_key, default_model=model)
    raw_content = await llm_client.complete_with_image(messages)
    return raw_content, parse_vision_response(raw_content)


async def enrich_ingredients(
    db: AsyncSession,
    user_id: uuid.UUID,
    vision_result: VisionResult,
) -> list[PhotoIngredient]:
    """Stage: map vision ingredients → dietary lookup rows (not yet persisted)."""
    lookup = IngredientLookupService(db)
    rows: list[PhotoIngredient] = []
    for vi in vision_result.ingredients:
        match = await lookup.lookup(vi.name)
        rows.append(
            PhotoIngredient(
                user_id=user_id,
                analysis_id=0,  # set in persist
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
        )
    return rows


def gate_status(vision_result: VisionResult) -> str:
    """Stage: confirmed vs needs_review."""
    return "needs_review" if analysis_needs_review(vision_result) else "confirmed"


async def persist_analysis(
    db: AsyncSession,
    analysis: PhotoAnalysis,
    user_id: uuid.UUID,
    raw_content: str,
    vision_result: VisionResult,
    ingredients: list[PhotoIngredient],
    status: str,
) -> None:
    """Stage: write analysis + ingredients and set terminal status."""
    analysis_crud = PhotoAnalysisCRUD(db)
    ingredient_crud = PhotoIngredientCRUD(db)

    # Replace prior ingredients on retry/reclaim (relationship is selectin-loaded).
    for ing in list(analysis.ingredients):
        await db.delete(ing)
    await db.flush()

    analysis.raw_response = raw_content
    analysis.dish_name = vision_result.dish_name
    analysis.cuisine = vision_result.cuisine
    analysis.dish_confidence = vision_result.confidence
    analysis.status = status

    for row in ingredients:
        row.analysis_id = analysis.id
        ingredient_crud.add(row)

    await analysis_crud.save()


async def run_staged_pipeline(
    photo_id: int,
    user_id: Optional[uuid.UUID] = None,
    *,
    meal_id: Optional[int] = None,
) -> Optional[str]:
    """Run extract → enrich → gate → persist → tag delivery.

    Returns terminal status string, or None if skipped without a terminal state.
    """
    analysis: Optional[PhotoAnalysis] = None
    try:
        async with async_session_maker() as db:
            loaded = await _load_photo_context(db, photo_id, user_id, meal_id=meal_id)
            if loaded.context is None:
                return loaded.terminal_status
            context = loaded.context
            analysis = context.analysis

            catalog_context = ""
            try:
                catalog_context = await build_catalog_context(db)
            except Exception:
                logger.warning(
                    "Failed to load catalog context for photo %d; continuing without catalog",
                    photo_id,
                    exc_info=True,
                )

            raw_content, vision_result = await extract_vision(
                context.photo,
                context.user_id_str,
                context.api_key,
                context.model,
                catalog_context,
            )
            ingredients = await enrich_ingredients(db, context.user_id, vision_result)
            status = gate_status(vision_result)
            await persist_analysis(
                db,
                analysis,
                context.user_id,
                raw_content,
                vision_result,
                ingredients,
                status,
            )
            await invalidate_user_insights_cache(context.user_id, context.photo.entry.date)

            logger.info(
                "Analysis complete for photo %d: %s status=%s (%d ingredients)",
                photo_id,
                vision_result.dish_name,
                status,
                len(ingredients),
            )

            if status == "confirmed" and context.photo.source_photo_id is None:
                from app.services.tag_delivery import TagDeliveryService

                try:
                    await TagDeliveryService().deliver_for_source(photo_id, context.user_id)
                except Exception:
                    logger.exception(
                        "Tag delivery failed for photo %d after confirmed analysis",
                        photo_id,
                    )
            return status

    except Exception as e:
        logger.exception("Food analysis failed for photo %d", photo_id)
        if analysis is not None:
            try:
                async with async_session_maker() as db:
                    await apply_session_user_id(db, analysis.user_id)
                    crud = PhotoAnalysisCRUD(db)
                    fresh = await crud.get_by_id(analysis.id)
                    if fresh:
                        fresh.status = "failed"
                        fresh.error_message = f"{type(e).__name__}: {str(e)[:200]}"
                        await crud.save()
            except Exception:
                logger.exception("Failed to update analysis status for photo %d", photo_id)
        raise


async def trigger_analysis_background(photo_id: int, user_id: Optional[uuid.UUID] = None) -> None:
    """Legacy BackgroundTasks entry point — runs the staged pipeline inline."""
    try:
        await run_staged_pipeline(photo_id, user_id)
    except Exception:
        pass  # status already marked failed inside run_staged_pipeline


class FoodAnalysisOrchestrator:
    """Coordinates the meal analysis pipeline.

    Prefer Airflow DAG trigger. ``run`` remains for BackgroundTasks / inline
    fallback and for tests that call the orchestrator directly.
    """

    async def run(self, photo_id: int, user_id: Optional[uuid.UUID] = None) -> None:
        await trigger_analysis_background(photo_id, user_id)
