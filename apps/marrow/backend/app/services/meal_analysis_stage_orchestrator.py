from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.invalidation import invalidate_user_insights_cache
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photos import PhotoCRUD
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.meal_analysis_stages import (
    EnrichRequest,
    EnrichResponse,
    ExtractResponse,
    FailRequest,
    FailResponse,
    GateRequest,
    GateResponse,
    IngredientPayload,
    PersistRequest,
    PersistResponse,
    StagePhotoRef,
)
from app.services.catalog_context import build_catalog_context
from app.services.food_analysis_orchestrator import (
    _load_photo_context,
    enrich_ingredients,
    extract_vision,
    gate_status,
    persist_analysis,
)
from app.services.vision_prompt import VisionResult
from f0rge_core.exceptions import NotFoundError, UnauthorizedError
from f0rge_db.tenant import apply_session_user_id

logger = logging.getLogger(__name__)


class MealAnalysisStageOrchestrator:
    """Coordinates Airflow stage HTTP handlers (extract→enrich→gate→persist)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def extract(self, body: StagePhotoRef) -> ExtractResponse:
        photo_id = body.photo_id
        user_id = body.user_id
        try:
            loaded = await _load_photo_context(self.db, photo_id, user_id)
            if loaded.context is None:
                return ExtractResponse(
                    analysis_id=0,
                    photo_id=photo_id,
                    user_id=user_id,
                    raw_content="",
                    vision=VisionResult(dish_name="skipped", confidence=0.0, ingredients=[]),
                    skipped=True,
                    skip_reason=loaded.terminal_status or "nothing_to_do",
                )
            context = loaded.context

            catalog_context = ""
            try:
                catalog_context = await build_catalog_context(self.db)
            except Exception:
                logger.warning(
                    "Failed to load catalog context for photo %d",
                    photo_id,
                    exc_info=True,
                )

            raw_content, vision = await extract_vision(
                context.photo,
                context.user_id_str,
                context.api_key,
                context.model,
                catalog_context,
            )
            return ExtractResponse(
                analysis_id=context.analysis.id,
                photo_id=photo_id,
                user_id=context.user_id,
                raw_content=raw_content,
                vision=vision,
            )
        except Exception as exc:
            await self._mark_failed_by_photo(photo_id, user_id, exc)
            raise

    async def enrich(self, body: EnrichRequest) -> EnrichResponse:
        await apply_session_user_id(self.db, body.user_id)
        rows = await enrich_ingredients(self.db, body.user_id, body.vision)
        return EnrichResponse(
            ingredients=[
                IngredientPayload(
                    name=r.name,
                    canonical_name=r.canonical_name,
                    visible=r.visible,
                    confidence=r.confidence,
                    histamine_score=r.histamine_score,
                    fodmap_oligos=r.fodmap_oligos,
                    fodmap_fructose=r.fodmap_fructose,
                    fodmap_polyols=r.fodmap_polyols,
                    fodmap_lactose=r.fodmap_lactose,
                    contains_gluten=r.contains_gluten,
                    contains_dairy=r.contains_dairy,
                )
                for r in rows
            ]
        )

    def gate(self, body: GateRequest) -> GateResponse:
        return GateResponse(status=gate_status(body.vision))

    async def persist(self, body: PersistRequest) -> PersistResponse:
        try:
            await apply_session_user_id(self.db, body.user_id)
            analysis_crud = PhotoAnalysisCRUD(self.db)
            analysis = await analysis_crud.get_by_id(body.analysis_id)
            if analysis is None:
                raise NotFoundError(f"Analysis {body.analysis_id} not found")

            photo = await PhotoCRUD(self.db).get_by_id(body.photo_id)
            if photo is None:
                raise NotFoundError(f"Photo {body.photo_id} not found")

            orm_ingredients = [
                PhotoIngredient(
                    user_id=body.user_id,
                    analysis_id=body.analysis_id,
                    name=ing.name,
                    canonical_name=ing.canonical_name,
                    visible=ing.visible,
                    confidence=ing.confidence,
                    user_edited=False,
                    histamine_score=ing.histamine_score,
                    fodmap_oligos=ing.fodmap_oligos,
                    fodmap_fructose=ing.fodmap_fructose,
                    fodmap_polyols=ing.fodmap_polyols,
                    fodmap_lactose=ing.fodmap_lactose,
                    contains_gluten=ing.contains_gluten,
                    contains_dairy=ing.contains_dairy,
                )
                for ing in body.ingredients
            ]
            await persist_analysis(
                self.db,
                analysis,
                body.user_id,
                body.raw_content,
                body.vision,
                orm_ingredients,
                body.status,
            )
            await invalidate_user_insights_cache(body.user_id, photo.entry.date)

            if body.status == "confirmed" and photo.source_photo_id is None:
                from app.services.tag_delivery import TagDeliveryService

                try:
                    await TagDeliveryService().deliver_for_source(body.photo_id, body.user_id)
                except Exception:
                    logger.exception(
                        "Tag delivery failed for photo %d after confirmed analysis",
                        body.photo_id,
                    )

            return PersistResponse(status=body.status, analysis_id=body.analysis_id)
        except Exception as exc:
            await self.db.rollback()
            await self.fail(
                FailRequest(
                    user_id=body.user_id,
                    analysis_id=body.analysis_id,
                    error_message=str(exc)[:500],
                )
            )
            raise

    async def fail(self, body: FailRequest) -> FailResponse:
        await apply_session_user_id(self.db, body.user_id)
        crud = PhotoAnalysisCRUD(self.db)
        analysis = await crud.get_by_id(body.analysis_id)
        if analysis is None:
            raise NotFoundError(f"Analysis {body.analysis_id} not found")
        analysis.status = "failed"
        analysis.error_message = body.error_message[:500]
        await crud.save()
        return FailResponse()

    async def _mark_failed_by_photo(
        self,
        photo_id: int,
        user_id: uuid.UUID,
        exc: BaseException,
    ) -> None:
        try:
            await self.db.rollback()
            await apply_session_user_id(self.db, user_id)
            photo = await PhotoCRUD(self.db).get_by_id(photo_id)
            if photo is None:
                return
            crud = PhotoAnalysisCRUD(self.db)
            analysis = await crud.get_by_meal_id(photo.meal_id)
            if analysis is None:
                return
            analysis.status = "failed"
            analysis.error_message = f"{type(exc).__name__}: {str(exc)[:200]}"
            await crud.save()
        except Exception:
            logger.exception("Failed to mark analysis failed for photo %d", photo_id)


def require_internal_token(provided: Optional[str], expected: str) -> None:
    if not expected:
        raise UnauthorizedError("MEAL_ANALYSIS_INTERNAL_TOKEN is not configured")
    if not provided or provided != expected:
        raise UnauthorizedError("Invalid meal analysis internal token")
