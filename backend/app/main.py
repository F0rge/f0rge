from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import async_session_maker
from app.middleware.auth import AuthContextMiddleware
from app.exceptions import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.routers import (
    auth,
    diet_tag_catalog,
    dietary_ingredient_catalog,
    enriched,
    entries,
    export,
    food_analysis,
    health_metrics,
    insights,
    lab_markers,
    labs,
    meals,
    medication_catalog,
    photos,
    settings as settings_router,
    supplement_catalog,
    symptom_catalog,
    trackers,
    treatments,
    weather,
)
from app.services.weather import weather_background_loop

logger = logging.getLogger(__name__)

_weather_task = None


def _warn_misconfigured_features() -> None:
    """Log a loud warning when a feature flag is on but its required
    credentials are missing. Catches deployments where the env var wasn't
    added to Coolify/the host but the flag stayed enabled."""
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


async def _seed_dietary_db_if_empty() -> None:
    """Seed the dietary reference tables from bundled JSON on first boot.

    Idempotent: if dietary_ingredients already has rows, skip silently. This
    is what unblocks food analysis on fresh deploys — without it, every
    ingredient renders as '?' because the lookup table is empty.

    Graceful: if the seed scripts or JSON files are missing (e.g. someone
    builds the image without the scripts/ COPY), log a warning and continue.
    The feature degrades to '?' badges rather than crashing the app.
    """
    from sqlalchemy import func, select

    from app.models.dietary_ingredient import DietaryIngredient

    async with async_session_maker() as session:
        existing = (
            await session.execute(select(func.count()).select_from(DietaryIngredient))
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
            count = (
                await session.execute(select(func.count()).select_from(DietaryIngredient))
            ).scalar_one()
        logger.info("Dietary seed complete: %d ingredients loaded", count)
    except Exception:
        logger.exception(
            "Dietary seed failed — analysis will show '?' for all ingredients "
            "until reseeded manually"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _weather_task
    await _seed_dietary_db_if_empty()
    _warn_misconfigured_features()
    if settings.weather_fetch_enabled and settings.openweathermap_api_key:
        _weather_task = asyncio.create_task(weather_background_loop())
    yield
    if _weather_task:
        _weather_task.cancel()


app = FastAPI(title="Health Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthContextMiddleware)


@app.exception_handler(NotFoundError)
async def _handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.detail})


@app.exception_handler(ValidationError)
async def _handle_validation(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": exc.detail})


@app.exception_handler(ConflictError)
async def _handle_conflict(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.detail})


@app.exception_handler(UnauthorizedError)
async def _handle_unauthorized(_: Request, exc: UnauthorizedError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": exc.detail})


@app.exception_handler(ExternalServiceError)
async def _handle_external_service(_: Request, exc: ExternalServiceError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": exc.detail})


app.include_router(auth.router)
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
app.include_router(symptom_catalog.router)
app.include_router(food_analysis.router)
app.include_router(insights.router)
app.include_router(treatments.router)
app.include_router(export.router)
app.include_router(labs.router)
app.include_router(settings_router.router)
app.include_router(lab_markers.router)
app.include_router(trackers.router)


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
