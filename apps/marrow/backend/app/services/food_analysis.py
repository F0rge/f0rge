from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from f0rge_core.exceptions import NotFoundError
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.food_analysis import DietaryConfirmUpdate, IngredientCreate, IngredientUpdate
from app.services.ingredient_lookup import IngredientLookupService
from app.services.tag_delivery import TagDeliveryService
from app.services.vision_prompt import VisionResult
from f0rge_db.tenant import current_user_id

if TYPE_CHECKING:
    from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator

DISH_CONFIDENCE_REVIEW_THRESHOLD = 0.7
INGREDIENT_CONFIDENCE_REVIEW_THRESHOLD = 0.5


def analysis_needs_review(vision_result: VisionResult) -> bool:
    """Return True when the user should review ingredients before confirming."""
    if vision_result.dish_name == "parse_error":
        return True
    if vision_result.confidence < DISH_CONFIDENCE_REVIEW_THRESHOLD:
        return True
    return any(
        ing.confidence < INGREDIENT_CONFIDENCE_REVIEW_THRESHOLD for ing in vision_result.ingredients
    )


class FoodAnalysisService:
    def __init__(self, db: AsyncSession, orchestrator: "FoodAnalysisOrchestrator") -> None:
        self.db = db
        self.analysis_crud = PhotoAnalysisCRUD(db)
        self.ingredient_crud = PhotoIngredientCRUD(db)
        self.orchestrator = orchestrator

    async def get_analysis(self, photo_id: int) -> Optional[PhotoAnalysis]:
        """Get canonical meal analysis for a photo placement."""
        return await self.analysis_crud.get_for_photo_with_ingredients(photo_id)

    async def confirm_analysis(self, analysis_id: int) -> PhotoAnalysis:
        """Set analysis status to confirmed."""
        analysis = await self.analysis_crud.get_by_id_with_ingredients(analysis_id)
        if not analysis:
            raise NotFoundError("Analysis not found")
        analysis.status = "confirmed"
        return await self.analysis_crud.commit_refresh(analysis)

    async def confirm_analysis_by_photo_id(
        self, photo_id: int, user_id: uuid.UUID
    ) -> PhotoAnalysis:
        """Confirm the shared meal analysis; tagger or recipient."""
        analysis = await self.get_analysis_or_404(photo_id)
        analysis.status = "confirmed"
        await self.analysis_crud.flush()
        photo = await PhotoCRUD(self.db).get_by_id_owned(photo_id)
        if photo is not None and photo.source_photo_id is None:
            await TagDeliveryService().deliver_for_source_in_transaction(self.db, photo_id, user_id)
        return await self.analysis_crud.commit_refresh(analysis)

    async def set_dietary_confirmations(
        self, photo_id: int, updates: DietaryConfirmUpdate
    ) -> PhotoAnalysis:
        """Set per-meal gluten-free / lactose-free overrides.

        Only the fields explicitly provided (non-None) are written, so a request
        toggling one flag never clobbers the other. Mirrors ``confirm_analysis``.
        """
        analysis = await self.get_analysis_or_404(photo_id)
        for key, value in updates.model_dump(exclude_none=True).items():
            setattr(analysis, key, value)
        return await self.analysis_crud.commit_refresh(analysis)

    async def update_ingredient(
        self, ingredient_id: int, updates: IngredientUpdate
    ) -> PhotoIngredient:
        """Update an ingredient and set user_edited flag."""
        ingredient = await self.ingredient_crud.get_by_id_for_editing(ingredient_id)
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

        return await self.ingredient_crud.commit_refresh(ingredient)

    async def add_ingredient(self, analysis_id: int, data: IngredientCreate) -> PhotoIngredient:
        """Add a manually-entered ingredient to an analysis."""
        analysis = await self.analysis_crud.get_by_id_for_editing(analysis_id)
        if not analysis:
            raise NotFoundError("Analysis not found")

        lookup = IngredientLookupService(self.db)
        match = await lookup.lookup(data.name)

        ingredient = PhotoIngredient(
            user_id=current_user_id(),
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
        self.ingredient_crud.add(ingredient)
        return await self.ingredient_crud.commit_refresh(ingredient)

    async def delete_analysis(self, analysis_id: int) -> None:
        """Delete an analysis and its ingredients (cascade)."""
        analysis = await self.analysis_crud.get_by_id_for_editing(analysis_id)
        if analysis:
            await self.analysis_crud.delete_and_commit(analysis)

    async def create_pending_analysis(self, photo_id: int) -> PhotoAnalysis:
        """Create a new pending analysis record for a photo."""
        photo = await PhotoCRUD(self.db).get_by_id(photo_id)
        if photo is None:
            raise NotFoundError(f"Photo {photo_id} not found")
        analysis = PhotoAnalysis(
            user_id=photo.user_id,
            meal_id=photo.meal_id,
            photo_id=photo_id,
            status="pending",
            model_id=settings.openrouter_model,
        )
        self.analysis_crud.add(analysis)
        return await self.analysis_crud.commit_refresh(analysis)

    async def delete_ingredient(self, ingredient_id: int) -> None:
        """Delete an ingredient by id."""
        ingredient = await self.ingredient_crud.get_by_id_for_editing(ingredient_id)
        if not ingredient:
            raise NotFoundError("Ingredient not found")
        await self.ingredient_crud.delete_and_commit(ingredient)

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
        photo = await PhotoCRUD(self.db).get_by_id(photo_id)
        if photo is None:
            raise NotFoundError(f"Photo {photo_id} not found")
        from app.services.food_analysis_enqueue import enqueue_food_analysis

        await enqueue_food_analysis(
            photo_id,
            photo.user_id,
            background_tasks,
            orchestrator_run=self.orchestrator.run,
        )
        return new_analysis

    async def add_ingredient_to_photo(
        self, photo_id: int, data: IngredientCreate
    ) -> PhotoIngredient:
        """Add ingredient to the analysis for the given photo; raises NotFoundError if no analysis."""
        analysis = await self.get_analysis(photo_id)
        if analysis is None:
            raise NotFoundError("No analysis found for this photo")
        return await self.add_ingredient(analysis.id, data)
