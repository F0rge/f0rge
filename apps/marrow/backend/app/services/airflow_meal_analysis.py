from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.invalidation import invalidate_user_insights_cache
from app.config import settings
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from f0rge_core.exceptions import NotFoundError, UnauthorizedError, ValidationError
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.airflow_meal import (
    MealAnalysisCompleteRequest,
    MealAnalysisResolveResponse,
)
from app.services.catalog_context import build_catalog_context
from app.services.ingredient_lookup import IngredientLookupService
from app.services.object_storage import build_object_key, object_storage_enabled
from app.services.vision_prompt import VisionIngredient, VisionResult
from f0rge_db.auth_context import user_id_ctx
from f0rge_db.tenant import apply_session_user_id

logger = logging.getLogger(__name__)


def validate_airflow_service_token(authorization: Optional[str]) -> None:
    """Require Bearer token matching AIRFLOW_SERVICE_TOKEN."""
    expected = settings.airflow_service_token
    if not expected:
        raise UnauthorizedError("AIRFLOW_SERVICE_TOKEN is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Not authenticated")
    if authorization[7:] != expected:
        raise UnauthorizedError("Invalid service token")


class AirflowMealAnalysisService:
    """HTTP seams for marrow_classify_meal_{dev,prod} DAGs (resolve / complete / fail)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.analysis_crud = PhotoAnalysisCRUD(db)
        self.ingredient_crud = PhotoIngredientCRUD(db)
        self.photo_crud = PhotoCRUD(db)

    async def resolve(self, photo_id: int, user_id_raw: str) -> MealAnalysisResolveResponse:
        try:
            user_id = uuid.UUID(user_id_raw)
        except ValueError as exc:
            raise ValidationError("Invalid user_id") from exc
        user_id_ctx.set(user_id)
        await apply_session_user_id(self.db, user_id)

        photo = await self.photo_crud.get_by_id(photo_id)
        if photo is None or photo.user_id != user_id:
            raise NotFoundError("Photo not found")
        if not photo.filename:
            raise ValidationError("Photo has no image file for vision analysis")
        if not settings.bucket_name or not object_storage_enabled():
            raise ValidationError("Object storage is not configured for Airflow meal analysis")

        existing = await self.analysis_crud.get_by_meal_id(photo.meal_id)
        if existing and existing.status not in ("pending", "failed"):
            raise ValidationError(
                f"Analysis already exists for photo {photo_id} (status={existing.status})"
            )

        if existing:
            analysis = existing
            analysis.status = "analyzing"
            analysis.error_message = None
            analysis.model_id = settings.openrouter_model
            if analysis.photo_id is None:
                analysis.photo_id = photo_id
        else:
            analysis = PhotoAnalysis(
                user_id=user_id,
                meal_id=photo.meal_id,
                photo_id=photo_id,
                status="analyzing",
                model_id=settings.openrouter_model,
            )
            self.analysis_crud.add(analysis)
        analysis = await self.analysis_crud.commit_refresh(analysis)

        catalog_context = ""
        try:
            catalog_context = await build_catalog_context(self.db)
        except Exception:
            logger.warning(
                "Failed to load catalog context for photo %d; continuing without catalog",
                photo_id,
                exc_info=True,
            )

        key = build_object_key(photo.filename, user_id=str(user_id))
        file_path = f"s3://{settings.bucket_name}/{key}"
        content_type = "image/jpeg"
        lower = photo.filename.lower()
        if lower.endswith(".png"):
            content_type = "image/png"
        elif lower.endswith(".webp"):
            content_type = "image/webp"

        return MealAnalysisResolveResponse(
            analysis_id=analysis.id,
            file_path=file_path,
            catalog_context=catalog_context,
            content_type=content_type,
        )

    async def complete(self, analysis_id: int, body: MealAnalysisCompleteRequest) -> dict[str, Any]:
        try:
            user_id = uuid.UUID(body.user_id)
        except ValueError as exc:
            raise ValidationError("Invalid user_id") from exc
        user_id_ctx.set(user_id)
        await apply_session_user_id(self.db, user_id)

        analysis = await self.analysis_crud.get_by_id(analysis_id)
        if analysis is None:
            raise NotFoundError("Analysis not found")

        vision = VisionResult(
            dish_name=body.dish_name,
            cuisine=body.cuisine,
            confidence=body.confidence,
            ingredients=[
                VisionIngredient(name=ing.name, visible=ing.visible, confidence=ing.confidence)
                for ing in body.ingredients
            ],
        )
        raw = vision.model_dump_json()

        # Replace any prior ingredient rows on retry.
        await self.ingredient_crud.delete_for_analysis(analysis_id)

        analysis.raw_response = raw
        analysis.dish_name = vision.dish_name
        analysis.cuisine = vision.cuisine
        analysis.dish_confidence = vision.confidence
        analysis.error_message = None

        lookup = IngredientLookupService(self.db)
        for vi in vision.ingredients:
            match = await lookup.lookup(vi.name)
            self.ingredient_crud.add(
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

        analysis.status = "confirmed"
        await self.analysis_crud.save()

        photo = await self.photo_crud.get_by_id(analysis.photo_id) if analysis.photo_id else None
        if photo is not None and photo.entry is not None:
            await invalidate_user_insights_cache(user_id, photo.entry.date)

        if photo is not None and photo.source_photo_id is None:
            from app.services.tag_delivery import TagDeliveryService

            try:
                await TagDeliveryService().deliver_for_source(photo.id, user_id)
            except Exception:
                logger.exception(
                    "Tag delivery failed for photo %s after Airflow analysis",
                    photo.id,
                )

        return {"analysis_id": analysis.id, "status": analysis.status}

    async def fail(
        self, analysis_id: int, error_message: str, user_id_raw: Optional[str] = None
    ) -> dict[str, Any]:
        if user_id_raw:
            try:
                user_id = uuid.UUID(user_id_raw)
            except ValueError as exc:
                raise ValidationError("Invalid user_id") from exc
            user_id_ctx.set(user_id)
            await apply_session_user_id(self.db, user_id)

        analysis = await self.analysis_crud.get_by_id(analysis_id)
        if analysis is None:
            raise NotFoundError("Analysis not found")
        if not user_id_raw:
            user_id_ctx.set(analysis.user_id)
            await apply_session_user_id(self.db, analysis.user_id)
        analysis.status = "failed"
        analysis.error_message = error_message[:500]
        await self.analysis_crud.save()
        return {"analysis_id": analysis.id, "status": "failed"}


async def trigger_classify_meal_dag(photo_id: int, user_id: uuid.UUID) -> Optional[str]:
    """POST dagRuns for AIRFLOW_CLASSIFY_DAG_ID. Returns dag_run_id or None."""
    base = settings.airflow_url.rstrip("/")
    if not base:
        raise ValidationError("AIRFLOW_URL is not configured")
    username = settings.airflow_username
    password = settings.airflow_password
    if not username or not password:
        raise ValidationError("AIRFLOW_USERNAME / AIRFLOW_PASSWORD are not configured")
    dag_id = settings.airflow_classify_dag_id
    if not dag_id:
        raise ValidationError("AIRFLOW_CLASSIFY_DAG_ID is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            f"{base}/auth/token",
            json={"username": username, "password": password},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        run_resp = await client.post(
            f"{base}/api/v2/dags/{dag_id}/dagRuns",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "logical_date": None,
                "conf": {"photo_id": photo_id, "user_id": str(user_id)},
            },
        )
        run_resp.raise_for_status()
        return run_resp.json().get("dag_run_id")
