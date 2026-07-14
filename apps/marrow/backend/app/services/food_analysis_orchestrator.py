from __future__ import annotations

import asyncio
import logging
import uuid
from typing import NamedTuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from app.database import async_session_maker
from f0rge_core.exceptions import NotFoundError
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.ingredient_lookup import IngredientLookupService
from app.services.vision_prompt import VisionResult, build_messages, parse_vision_response
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


async def _load_photo_context(
    db: AsyncSession, photo_id: int, user_id: Optional[uuid.UUID]
) -> Optional[_PhotoContext]:
    """Resolve the owner + LLM credentials and flip the analysis row to "analyzing".

    Returns None when there's nothing left to do: missing photo, no API key
    configured (marks the analysis "failed" and commits before returning), or
    an analysis already running/finished for this photo. The "analyzing"
    status flip is committed here on its own, before the slow LLM call --
    that's what lets a later invocation see "analyzing" and skip a duplicate
    run instead of racing it (Rule 6.6, issue #225).
    """
    analysis_crud = PhotoAnalysisCRUD(db)
    photo_crud = PhotoCRUD(db)

    if user_id is None:
        resolved = await photo_crud.get_user_id(photo_id)
        if resolved is None:
            logger.warning("Skipping analysis for missing photo %d", photo_id)
            return None
        user_id = resolved
    user_id_str = str(user_id)
    await apply_session_user_id(db, user_id)

    photo = await photo_crud.get_by_id(photo_id)
    if not photo:
        logger.warning("Skipping analysis for missing photo %d", photo_id)
        return None

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
        return None

    # Reuse a pending record or skip if already running/finished.
    existing = await analysis_crud.get_by_meal_id(photo.meal_id)

    if existing and existing.status not in ("pending", "failed"):
        logger.info(
            "Analysis already exists for photo %d (status=%s), skipping",
            photo_id,
            existing.status,
        )
        return None

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

    return _PhotoContext(
        analysis=analysis,
        photo=photo,
        user_id=user_id,
        user_id_str=user_id_str,
        model=model,
        api_key=api_key,
    )


async def _run_vision(
    photo: Photo, user_id_str: str, api_key: str, model: str
) -> tuple[str, VisionResult]:
    """Read the photo off disk and get the vision model's structured read on it.

    Pure I/O, no DB access: a disk read (blocking, wrapped in a thread) plus
    the OpenRouter call. Raises NotFoundError if the file is missing on disk.
    """
    from app.services.photo_storage import photo_exists, read_photo

    if not photo_exists(photo.filename, user_id=user_id_str):
        raise NotFoundError(f"Photo file not found: {photo.filename}")

    image_bytes = await asyncio.to_thread(read_photo, photo.filename, user_id=user_id_str)
    messages = build_messages(image_bytes)

    from app.services.llm.openrouter import OpenRouterClient

    llm_client = OpenRouterClient(api_key=api_key, default_model=model)
    raw_content = await llm_client.complete_with_image(messages)

    return raw_content, parse_vision_response(raw_content)


async def _persist_analysis(
    db: AsyncSession,
    analysis: PhotoAnalysis,
    user_id: uuid.UUID,
    raw_content: str,
    vision_result: VisionResult,
) -> None:
    """Write the vision result and its ingredients onto the analysis row."""
    analysis_crud = PhotoAnalysisCRUD(db)
    ingredient_crud = PhotoIngredientCRUD(db)

    analysis.raw_response = raw_content
    analysis.dish_name = vision_result.dish_name
    analysis.cuisine = vision_result.cuisine
    analysis.dish_confidence = vision_result.confidence

    lookup = IngredientLookupService(db)
    for vi in vision_result.ingredients:
        match = await lookup.lookup(vi.name)
        ingredient_crud.add(
            PhotoIngredient(
                user_id=user_id,
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
        )

    # Auto-confirm on completion: the manual "Confirm" step was removed from the
    # UI, and "confirmed" is what gates diet-flags, insights, meals, and tagged-
    # meal delivery. Ingredients stay fully editable afterward.
    analysis.status = "confirmed"
    await analysis_crud.save()


async def trigger_analysis_background(photo_id: int, user_id: Optional[uuid.UUID] = None) -> None:
    """Run food photo analysis in a background task.

    Opens its own DB session because FastAPI BackgroundTasks execute
    after the response is sent and the request session is closed.
    """
    analysis: Optional[PhotoAnalysis] = None
    try:
        async with async_session_maker() as db:
            context = await _load_photo_context(db, photo_id, user_id)
            if context is None:
                return
            analysis = context.analysis

            raw_content, vision_result = await _run_vision(
                context.photo, context.user_id_str, context.api_key, context.model
            )
            await _persist_analysis(db, analysis, context.user_id, raw_content, vision_result)

            logger.info(
                "Analysis complete for photo %d: %s (%d ingredients)",
                photo_id,
                vision_result.dish_name,
                len(vision_result.ingredients),
            )

            # The analysis just auto-confirmed, which is what used to trigger
            # tagged-meal delivery via the manual confirm endpoint. Fire it here
            # instead (fresh session; safe no-op when there are no pending tags).
            # Canonical photos only — delivered copies are never re-delivered.
            if context.photo.source_photo_id is None:
                from app.services.tag_delivery import TagDeliveryService

                await TagDeliveryService().deliver_for_source(photo_id, context.user_id)

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
                        # Full traceback is already in logs via logger.exception above.
                        # Store only a short human-readable summary so the UI doesn't
                        # display a raw multi-line stack trace.
                        fresh.error_message = f"{type(e).__name__}: {str(e)[:200]}"
                        await crud.save()
            except Exception:
                logger.exception("Failed to update analysis status for photo %d", photo_id)


class FoodAnalysisOrchestrator:
    """Coordinates the background analysis pipeline (Rule 9.4): photo storage
    read, vision LLM call, and PhotoAnalysis/PhotoIngredient persistence.

    Stateless -- takes no DB session at construction time, because it's invoked
    via FastAPI BackgroundTasks after the request session has already closed
    and must open its own session per run (see ``trigger_analysis_background``).
    """

    async def run(self, photo_id: int, user_id: Optional[uuid.UUID] = None) -> None:
        await trigger_analysis_background(photo_id, user_id)
