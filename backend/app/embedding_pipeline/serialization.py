from __future__ import annotations

from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.lab import Lab
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.models.treatment import Treatment
from app.services.diet_flags import compute_photo_signal, parse_diet_risk_csv


async def serialize_entry(db: AsyncSession, source_id: int) -> Optional[str]:
    """Return the canonical text for an entry row, or None if deleted."""
    result = await db.execute(select(Entry).where(Entry.id == source_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None

    parts = [f"Health log entry for {row.date}"]
    if row.notes:
        parts.append(f"Notes: {row.notes}")
    parts.append(f"Overall: {row.overall}/10")
    parts.append(f"Bloating: {row.bloating}/10")
    parts.append(f"Joint pain: {row.joint_pain}/10")
    parts.append(f"Neuro: {row.neuro}/10")
    parts.append(f"Sleep quality: {row.sleep_quality}/10")
    parts.append(f"Stress: {row.stress}/10")
    _effective = sorted(
        compute_photo_signal(row).flags | parse_diet_risk_csv(row.diet_risk)
    )
    parts.append(f"Diet risk: {', '.join(_effective) if _effective else 'normal'}")
    parts.append(f"Sick: {row.sick}")
    if row.stool_status:
        parts.append(f"Stool status: {row.stool_status}")
    if row.symptoms_json:
        symptom_str = ", ".join(f"{k}: {v}" for k, v in row.symptoms_json.items())
        parts.append(f"Symptoms: {symptom_str}")
    if row.alcohol_units:
        parts.append(f"Alcohol units: {row.alcohol_units}")
    if row.caffeine_servings:
        parts.append(f"Caffeine servings: {row.caffeine_servings}")
    return "\n".join(parts)


async def serialize_lab(db: AsyncSession, source_id: int) -> Optional[str]:
    """Return the canonical text for a lab row (uses raw_text), or None if deleted."""
    result = await db.execute(select(Lab).where(Lab.id == source_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None

    parts = [f"Lab report: {row.name} ({row.type}) on {row.lab_date}"]
    if row.raw_text:
        parts.append(row.raw_text)
    if row.notes:
        parts.append(f"Notes: {row.notes}")
    return "\n".join(parts)


async def serialize_treatment(db: AsyncSession, source_id: int) -> Optional[str]:
    """Return the canonical text for a treatment row, or None if deleted."""
    result = await db.execute(select(Treatment).where(Treatment.id == source_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None

    parts = [f"Treatment: {row.name} (type: {row.type})"]
    parts.append(f"Started: {row.start_date}")
    if row.end_date:
        parts.append(f"Ended: {row.end_date}")
    if row.dose:
        parts.append(f"Dose: {row.dose}")
    if row.notes:
        parts.append(f"Notes: {row.notes}")
    return "\n".join(parts)


async def serialize_photo_analysis(db: AsyncSession, source_id: int) -> Optional[str]:
    """Return the canonical text for a photo_analysis row (joins photo_ingredients)."""
    result = await db.execute(
        select(PhotoAnalysis).where(PhotoAnalysis.id == source_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    parts = []
    if row.dish_name:
        parts.append(f"Food photo analysis: {row.dish_name}")
    if row.cuisine:
        parts.append(f"Cuisine: {row.cuisine}")
    if row.raw_response:
        parts.append(f"Analysis: {row.raw_response}")

    # Fetch ingredients separately (lazy="selectin" should handle it, but be explicit).
    ingredients_result = await db.execute(
        select(PhotoIngredient).where(PhotoIngredient.analysis_id == source_id)
    )
    ingredients = ingredients_result.scalars().all()
    if ingredients:
        ingredient_names = [i.name for i in ingredients if i.visible]
        if ingredient_names:
            parts.append(f"Ingredients: {', '.join(ingredient_names)}")

    if not parts:
        return None
    return "\n".join(parts)


# Dispatch table: source_table name → serializer function.
# The worker uses this to look up the right function by table name.
SERIALIZERS: dict[str, Callable[[AsyncSession, int], object]] = {
    "entries": serialize_entry,
    "labs": serialize_lab,
    "treatments": serialize_treatment,
    "photo_analyses": serialize_photo_analysis,
}
