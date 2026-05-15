from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.routers import (
    auth,
    enriched,
    entries,
    export,
    food_analysis,
    health_metrics,
    photos,
    supplement_catalog,
    treatments,
    weather,
)
from app.services.weather import weather_background_loop

logger = logging.getLogger(__name__)

_weather_task = None

DEFAULT_SUPPLEMENTS = [
    ("nac", "NAC"),
    ("fish_oil", "Fish Oil"),
    ("magnesium", "Magnesium"),
    ("beef_organs", "Beef Organs"),
    ("allicin", "Allicin"),
    ("oregano", "Oregano Oil"),
    ("vitamin_d_k2", "D3 + K2"),
    ("dao", "DAO"),
    ("creatine", "Creatine"),
]


def _run_migrations() -> None:
    """Add any missing columns to existing tables."""
    import sqlite3
    from app.config import settings

    db_path = settings.database_url.replace("sqlite:///", "")
    if not db_path or "sqlite" not in settings.database_url:
        return
    try:
        conn = sqlite3.connect(db_path)
        # Entries table migrations
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()
        }
        if "stool_type" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN stool_type VARCHAR")
        if "schema_version" not in existing:
            # Existing rows are v1 (coarse stool + no entry_time).
            conn.execute(
                "ALTER TABLE entries ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1"
            )
        if "entry_time" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN entry_time DATETIME")
        if "period_of_day" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN period_of_day VARCHAR")
        if "stool_status" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN stool_status VARCHAR")
        if "bristol_type" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN bristol_type INTEGER")
        if "hot_shower" not in existing:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN hot_shower BOOLEAN NOT NULL DEFAULT 0"
            )
        if "alcohol_units" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN alcohol_units INTEGER")
        if "caffeine_servings" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN caffeine_servings INTEGER")

        # Photos table migrations
        photo_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(photos)").fetchall()
        }
        if "meal_time" not in photo_cols:
            conn.execute("ALTER TABLE photos ADD COLUMN meal_time DATETIME")
            # Backfill: existing photos get created_at as their meal_time.
            conn.execute(
                "UPDATE photos SET meal_time = created_at WHERE meal_time IS NULL"
            )

        # Health metrics table migrations
        try:
            hm_cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(health_metrics)").fetchall()
            }
            for col in [
                "sleep_deep_min",
                "sleep_rem_min",
                "sleep_core_min",
                "sleep_awake_min",
                "sleep_efficiency",
                "sleep_start",
                "sleep_end",
            ]:
                if col not in hm_cols:
                    col_type = (
                        "VARCHAR"
                        if col.startswith("sleep_s") or col.startswith("sleep_e")
                        else "FLOAT"
                    )
                    conn.execute(
                        f"ALTER TABLE health_metrics ADD COLUMN {col} {col_type}"
                    )
        except Exception:
            pass  # Table may not exist yet

        conn.commit()
        conn.close()
    except Exception:
        pass  # Table may not exist yet, create_all will handle it


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


def _seed_supplement_catalog() -> None:
    """Seed the supplement_catalog table with the default list on first boot."""
    from sqlalchemy.orm import Session

    from app.models.supplement_catalog import SupplementCatalogItem

    with Session(engine) as session:
        existing_count = session.query(SupplementCatalogItem).count()
        if existing_count > 0:
            return
        for sort_order, (key, label) in enumerate(DEFAULT_SUPPLEMENTS):
            session.add(
                SupplementCatalogItem(key=key, label=label, sort_order=sort_order)
            )
        session.commit()


def _seed_dietary_db_if_empty() -> None:
    """Seed the dietary reference tables from bundled JSON on first boot.

    Idempotent: if dietary_ingredients already has rows, skip silently. This
    is what unblocks food analysis on fresh deploys — without it, every
    ingredient renders as '?' because the lookup table is empty.

    Graceful: if the seed scripts or JSON files are missing (e.g. someone
    builds the image without the scripts/ COPY), log a warning and continue.
    The feature degrades to '?' badges rather than crashing the app.
    """
    from sqlalchemy.orm import Session

    from app.models.dietary_ingredient import DietaryIngredient

    with Session(engine) as session:
        existing = session.query(DietaryIngredient).count()

    if existing > 0:
        logger.info(
            "Dietary tables already seeded (%d ingredients) — skipping",
            existing,
        )
        return

    logger.warning(
        "Dietary tables empty — seeding from bundled JSON. "
        "This runs once on a fresh data volume."
    )
    try:
        from scripts.seed_dietary_db import main as seed_main

        seed_main()
        with Session(engine) as session:
            count = session.query(DietaryIngredient).count()
        logger.info("Dietary seed complete: %d ingredients loaded", count)
    except Exception:
        logger.exception(
            "Dietary seed failed — analysis will show '?' for all ingredients "
            "until reseeded manually"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _weather_task
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _seed_supplement_catalog()
    _seed_dietary_db_if_empty()
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


@app.exception_handler(NotFoundError)
async def _handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.detail}
    )


@app.exception_handler(ValidationError)
async def _handle_validation(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": exc.detail}
    )


@app.exception_handler(ConflictError)
async def _handle_conflict(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": exc.detail}
    )


app.include_router(auth.router)
app.include_router(entries.router)
app.include_router(photos.router)
app.include_router(weather.router)
app.include_router(health_metrics.router)
app.include_router(enriched.router)
app.include_router(supplement_catalog.router)
app.include_router(food_analysis.router)
app.include_router(treatments.router)
app.include_router(export.router)


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
