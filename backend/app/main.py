from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, enriched, entries, health_metrics, photos, weather
from app.services.weather import weather_background_loop

_weather_task = None


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
        existing = {row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()}
        if "stool_type" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN stool_type VARCHAR")

        # Health metrics table migrations
        try:
            hm_cols = {row[1] for row in conn.execute("PRAGMA table_info(health_metrics)").fetchall()}
            for col in ["sleep_deep_min", "sleep_rem_min", "sleep_core_min", "sleep_awake_min",
                        "sleep_efficiency", "sleep_start", "sleep_end"]:
                if col not in hm_cols:
                    col_type = "VARCHAR" if col.startswith("sleep_s") or col.startswith("sleep_e") else "FLOAT"
                    conn.execute(f"ALTER TABLE health_metrics ADD COLUMN {col} {col_type}")
        except Exception:
            pass  # Table may not exist yet

        conn.commit()
        conn.close()
    except Exception:
        pass  # Table may not exist yet, create_all will handle it


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _weather_task
    Base.metadata.create_all(bind=engine)
    _run_migrations()
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

app.include_router(auth.router)
app.include_router(entries.router)
app.include_router(photos.router)
app.include_router(weather.router)
app.include_router(health_metrics.router)
app.include_router(enriched.router)


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
