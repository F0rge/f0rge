from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import SessionLocal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.schemas.food_analysis import IngredientCreate, IngredientUpdate
from app.services.ingredient_lookup import IngredientLookupService
from app.services.obsidian import write_daily_file
from app.services.vision_prompt import build_messages, parse_vision_response

logger = logging.getLogger(__name__)


class FoodAnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_analysis(self, photo_id: int) -> Optional[PhotoAnalysis]:
        """Get analysis for a photo, with eagerly loaded ingredients."""
        return (
            self.db.query(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients))
            .filter(PhotoAnalysis.photo_id == photo_id)
            .first()
        )

    def confirm_analysis(self, analysis_id: int) -> PhotoAnalysis:
        """Set analysis status to confirmed and re-render vault."""
        analysis = (
            self.db.query(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients))
            .filter(PhotoAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            raise HTTPException(404, "Analysis not found")
        analysis.status = "confirmed"
        self.db.commit()
        self.db.refresh(analysis)
        self._rerender_vault(analysis.photo_id)
        return analysis

    def update_ingredient(
        self, ingredient_id: int, updates: IngredientUpdate
    ) -> PhotoIngredient:
        """Update an ingredient and set user_edited flag."""
        ingredient = (
            self.db.query(PhotoIngredient)
            .filter(PhotoIngredient.id == ingredient_id)
            .first()
        )
        if not ingredient:
            raise HTTPException(404, "Ingredient not found")

        update_data = updates.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(ingredient, key, value)
        ingredient.user_edited = True

        # If name changed and no canonical_name override, re-lookup
        if "name" in update_data and "canonical_name" not in update_data:
            lookup = IngredientLookupService(self.db)
            match = lookup.lookup(ingredient.name)
            if match:
                ingredient.canonical_name = match.canonical_name
                ingredient.histamine_score = match.histamine_score
                ingredient.fodmap_oligos = match.fodmap_oligos
                ingredient.fodmap_fructose = match.fodmap_fructose
                ingredient.fodmap_polyols = match.fodmap_polyols
                ingredient.fodmap_lactose = match.fodmap_lactose
                ingredient.contains_gluten = match.contains_gluten
                ingredient.contains_dairy = match.contains_dairy

        self.db.commit()
        self.db.refresh(ingredient)
        return ingredient

    def add_ingredient(
        self, analysis_id: int, data: IngredientCreate
    ) -> PhotoIngredient:
        """Add a manually-entered ingredient to an analysis."""
        analysis = (
            self.db.query(PhotoAnalysis).filter(PhotoAnalysis.id == analysis_id).first()
        )
        if not analysis:
            raise HTTPException(404, "Analysis not found")

        # Lookup dietary data
        lookup = IngredientLookupService(self.db)
        match = lookup.lookup(data.name)

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
        self.db.commit()
        self.db.refresh(ingredient)
        return ingredient

    def delete_analysis(self, analysis_id: int) -> None:
        """Delete an analysis and its ingredients (cascade)."""
        analysis = (
            self.db.query(PhotoAnalysis).filter(PhotoAnalysis.id == analysis_id).first()
        )
        if analysis:
            self.db.delete(analysis)
            self.db.commit()

    def create_pending_analysis(self, photo_id: int) -> PhotoAnalysis:
        """Create a new pending analysis record for a photo."""
        analysis = PhotoAnalysis(
            photo_id=photo_id,
            status="pending",
            model_id=settings.openrouter_model,
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def delete_ingredient(self, ingredient_id: int) -> None:
        """Delete an ingredient by id."""
        ingredient = (
            self.db.query(PhotoIngredient)
            .filter(PhotoIngredient.id == ingredient_id)
            .first()
        )
        if not ingredient:
            raise HTTPException(404, "Ingredient not found")
        self.db.delete(ingredient)
        self.db.commit()

    def _rerender_vault(self, photo_id: int) -> None:
        """Re-render the Obsidian vault file for the entry owning this photo."""
        photo = self.db.query(Photo).filter(Photo.id == photo_id).first()
        if photo and photo.entry:
            entry = photo.entry
            self.db.refresh(entry)
            write_daily_file(self.db, entry, entry.photos)


# ---------------------------------------------------------------------------
# Background trigger (runs outside request lifecycle)
# ---------------------------------------------------------------------------


def trigger_analysis_background(photo_id: int) -> None:
    """Run food photo analysis in a background task.

    Creates its own DB session because FastAPI BackgroundTasks execute
    after the response is sent and the request session is closed.
    """
    db: Session = SessionLocal()
    analysis: Optional[PhotoAnalysis] = None
    try:
        # Ensure no existing analysis for this photo
        existing = (
            db.query(PhotoAnalysis).filter(PhotoAnalysis.photo_id == photo_id).first()
        )
        if existing:
            logger.info(
                "Analysis already exists for photo %d (status=%s), skipping",
                photo_id,
                existing.status,
            )
            return

        # Create analysis record
        analysis = PhotoAnalysis(
            photo_id=photo_id,
            status="analyzing",
            model_id=settings.openrouter_model,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        # Read photo file from disk
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if not photo:
            raise ValueError(f"Photo {photo_id} not found in database")

        photo_path = os.path.join(settings.photo_dir, photo.filename)
        if not os.path.exists(photo_path):
            raise FileNotFoundError(f"Photo file not found: {photo_path}")

        with open(photo_path, "rb") as f:
            image_bytes = f.read()

        # Build vision prompt and call OpenRouter
        messages = build_messages(image_bytes)

        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openrouter_model,
                "messages": messages,
            },
            timeout=60.0,
        )
        response.raise_for_status()

        raw_content = response.json()["choices"][0]["message"]["content"]
        analysis.raw_response = raw_content

        # Parse the vision response
        vision_result = parse_vision_response(raw_content)

        analysis.dish_name = vision_result.dish_name
        analysis.cuisine = vision_result.cuisine
        analysis.dish_confidence = vision_result.confidence

        # Create ingredient records with dietary lookup
        lookup = IngredientLookupService(db)
        for vi in vision_result.ingredients:
            match = lookup.lookup(vi.name)
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
        db.commit()

        # Re-render Obsidian vault file
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo and photo.entry:
            entry = photo.entry
            db.refresh(entry)
            write_daily_file(db, entry, entry.photos)

        logger.info(
            "Analysis complete for photo %d: %s (%d ingredients)",
            photo_id,
            vision_result.dish_name,
            len(vision_result.ingredients),
        )

    except Exception:
        logger.exception("Food analysis failed for photo %d", photo_id)
        if analysis:
            try:
                analysis.status = "failed"
                analysis.error_message = str(__import__("traceback").format_exc())
                db.commit()
            except Exception:
                logger.exception(
                    "Failed to update analysis status for photo %d", photo_id
                )
    finally:
        db.close()
