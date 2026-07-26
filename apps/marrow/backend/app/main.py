from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from f0rge_core.handlers import register_exception_handlers

from app.config import settings
from app.database import async_session_maker
from app.logging_config import JsonFormatter
from app.middleware.auth import AuthContextMiddleware
from app.middleware.request_id import RequestIdFilter, RequestIdMiddleware
from app.routers import (
    account,
    auth,
    cache,
    devices,
    diet_tag_catalog,
    dietary_ingredient_catalog,
    enriched,
    entries,
    export,
    food_analysis,
    health_metrics,
    internal_meal_analysis,
    insights,
    lab_markers,
    labs,
    meals,
    medication_catalog,
    notifications,
    onboarding,
    photos,
    settings as settings_router,
    signals,
    social,
    supplement_catalog,
    symptom_catalog,
    trackers,
    treatments,
    weather,
)
from app.services.push import apns_configured
from app.services.reminders import reminder_background_loop
from app.services.weather import weather_background_loop

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def _maybe_init_sentry() -> None:
    dsn = getattr(settings, "sentry_dsn", "") or ""
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(dsn=dsn, integrations=[FastApiIntegration()], traces_sample_rate=0.0)
        logger.info("Sentry initialized")
    except Exception:
        logger.exception("Sentry init failed — continuing without error tracking")


_configure_logging()
_maybe_init_sentry()

_weather_task = None
_reminder_task = None


def _warn_misconfigured_features() -> None:
    """Log a loud warning when a feature flag is on but its required
    credentials are missing. Catches deployments where the env var wasn't
    added to the host but the flag stayed enabled."""
    if settings.food_analysis_enabled and not settings.openrouter_api_key:
        logger.warning(
            "FOOD_ANALYSIS_ENABLED=true but OPENROUTER_API_KEY is empty. "
            "Photo analysis will be marked as failed for every upload. "
            "Either set OPENROUTER_API_KEY or set FOOD_ANALYSIS_ENABLED=false."
        )
    if settings.weather_fetch_enabled and not settings.openweathermap_api_key:
        logger.warning(
            "WEATHER_FETCH_ENABLED=true but OPENWEATHERMAP_API_KEY is empty. "
            "Weather background loop will not start."
        )
    if settings.dose_reminders_enabled and not apns_configured():
        logger.warning(
            "DOSE_REMINDERS_ENABLED=true but APNS_KEY_ID/APNS_TEAM_ID/APNS_PRIVATE_KEY "
            "are not all set. Push delivery is disabled; in-app reminder "
            "notifications still work."
        )


async def _seed_dietary_db_if_empty() -> None:
    """Seed the dietary reference tables from bundled JSON on first boot.

    Idempotent: if dietary_ingredients already has rows, skip silently. This
    is what unblocks food analysis on fresh deploys — without it, every
    ingredient renders as '?' because the lookup table is empty.

    Graceful: if the seed scripts or JSON files are missing (e.g. someone
    builds the image without the scripts/ COPY), log a warning and continue.
    The feature degrades to '?' badges rather than crashing the app.
    """
    import uuid

    from sqlalchemy import func, select

    from app.models.dietary_ingredient import DietaryIngredient
    from f0rge_db.tenant import apply_session_user_id

    ref_user_id = uuid.UUID(settings.default_storage_user_id)

    async with async_session_maker() as session:
        await apply_session_user_id(session, ref_user_id)
        existing = (
            await session.execute(
                select(func.count())
                .select_from(DietaryIngredient)
                .where(DietaryIngredient.user_id == ref_user_id)
            )
        ).scalar_one()

    if existing > 0:
        logger.info(
            "Dietary tables already seeded (%d ingredients) — skipping",
            existing,
        )
        return

    logger.warning(
        "Dietary tables empty — seeding from bundled JSON. This runs once on a fresh data volume."
    )
    try:
        from scripts.seed_dietary_db import main as seed_main

        await asyncio.to_thread(seed_main)
        async with async_session_maker() as session:
            await apply_session_user_id(session, ref_user_id)
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(DietaryIngredient)
                    .where(DietaryIngredient.user_id == ref_user_id)
                )
            ).scalar_one()
        logger.info("Dietary seed complete: %d ingredients loaded", count)
    except Exception:
        logger.exception(
            "Dietary seed failed — analysis will show '?' for all ingredients "
            "until reseeded manually"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _weather_task, _reminder_task
    await _seed_dietary_db_if_empty()
    _warn_misconfigured_features()
    if settings.weather_fetch_enabled and settings.openweathermap_api_key:
        _weather_task = asyncio.create_task(weather_background_loop())
    if settings.dose_reminders_enabled:
        _reminder_task = asyncio.create_task(reminder_background_loop())
    yield
    if _weather_task:
        _weather_task.cancel()
    if _reminder_task:
        _reminder_task.cancel()


app = FastAPI(title="Marrow", lifespan=lifespan)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthContextMiddleware)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(cache.router)
app.include_router(account.router)
app.include_router(devices.router)
app.include_router(entries.router)
app.include_router(photos.router)
app.include_router(meals.router)
app.include_router(weather.router)
app.include_router(health_metrics.router)
app.include_router(enriched.router)
app.include_router(supplement_catalog.router)
app.include_router(diet_tag_catalog.router)
app.include_router(dietary_ingredient_catalog.router)
app.include_router(medication_catalog.router)
app.include_router(onboarding.router)
app.include_router(symptom_catalog.router)
app.include_router(food_analysis.router)
app.include_router(internal_meal_analysis.router)
app.include_router(insights.router)
app.include_router(signals.router)
app.include_router(treatments.router)
app.include_router(export.router)
app.include_router(labs.router)
app.include_router(settings_router.router)
app.include_router(lab_markers.router)
app.include_router(trackers.router)
app.include_router(social.router)
app.include_router(notifications.router)


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
