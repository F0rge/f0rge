from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, entries, photos


def _run_migrations() -> None:
    """Add any missing columns to existing tables."""
    import sqlite3
    from app.config import settings

    db_path = settings.database_url.replace("sqlite:///", "")
    if not db_path or "sqlite" not in settings.database_url:
        return
    try:
        conn = sqlite3.connect(db_path)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()}
        if "stool_type" not in existing:
            conn.execute("ALTER TABLE entries ADD COLUMN stool_type VARCHAR")
            conn.commit()
        conn.close()
    except Exception:
        pass  # Table may not exist yet, create_all will handle it


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    yield


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


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
