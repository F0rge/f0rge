"""Async helper to pre-fetch all data needed for Obsidian vault rendering.

Callers await this, then pass the results to asyncio.to_thread(write_daily_file, ...).
This keeps obsidian.write_daily_file session-free (safe to run in a thread).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.medication_catalog import MedicationCatalogItem
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.treatment import Treatment
from app.services.obsidian import write_daily_file
from app.services.weather import get_daily_summary

logger = logging.getLogger(__name__)


async def _fetch_obsidian_deps(
    db: AsyncSession,
    entry: Entry,
    photos: Sequence[Photo],
) -> tuple[
    dict[int, PhotoAnalysis],
    dict[str, str],
    list[Treatment],
    Optional[object],  # HealthMetric
    Optional[object],  # WeatherDailySummary
    dict[str, str],  # med_labels
]:
    """Fetch all data needed by write_daily_file in parallel where possible."""
    photo_ids = [p.id for p in photos]

    # --- analyses ---
    analyses: dict[int, PhotoAnalysis] = {}
    if photo_ids:
        result = await db.execute(
            select(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients))
            .where(
                PhotoAnalysis.photo_id.in_(photo_ids),
                PhotoAnalysis.status == "confirmed",
            )
        )
        for a in result.scalars().all():
            analyses[a.photo_id] = a

    # --- active symptom labels ---
    sym_result = await db.execute(
        select(SymptomCatalogItem).where(SymptomCatalogItem.archived.is_(False))
    )
    active_sym_labels: dict[str, str] = {s.key: s.label for s in sym_result.scalars().all()}

    # --- medication labels (active AND archived) ---
    # Unlike symptoms, this is not filtered to active-only: a historical entry
    # that logged an archived medication must still render its label.
    med_result = await db.execute(select(MedicationCatalogItem))
    med_labels: dict[str, str] = {m.key: m.label for m in med_result.scalars().all()}

    # --- active treatments ---
    tx_result = await db.execute(
        select(Treatment)
        .where(
            Treatment.start_date <= entry.date,
            (Treatment.end_date.is_(None)) | (Treatment.end_date >= entry.date),
        )
        .order_by(Treatment.name)
    )
    active_treatments: list[Treatment] = list(tx_result.scalars().all())

    # --- health metric ---
    hm_result = await db.execute(select(HealthMetric).where(HealthMetric.date == entry.date))
    health = hm_result.scalar_one_or_none()

    # --- weather summary ---
    try:
        weather = await get_daily_summary(db, entry.date)
    except Exception:
        logger.exception("Failed to fetch weather summary for %s", entry.date)
        weather = None

    return analyses, active_sym_labels, active_treatments, health, weather, med_labels


async def render_and_write_daily_file(
    db: AsyncSession,
    entry: Entry,
    photos: Sequence[Photo],
) -> None:
    """Fetch all needed data, then write the vault file in a thread."""
    if not entry:
        return
    (
        analyses,
        active_sym_labels,
        active_treatments,
        health,
        weather,
        med_labels,
    ) = await _fetch_obsidian_deps(db, entry, photos)
    await asyncio.to_thread(
        write_daily_file,
        entry,
        list(photos),
        analyses,
        active_sym_labels,
        active_treatments,
        health,
        weather,
        med_labels,
    )
