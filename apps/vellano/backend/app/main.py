from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from f0rge_core.handlers import register_exception_handlers

from app.config import settings
from app.database import async_session_maker
from app.middleware.auth import AuthContextMiddleware
from app.routers import auth, health, locations, users
from app.services.locations import LocationSeedService
from app.services.users import BootstrapService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await BootstrapService(session).seed_if_empty()
        await LocationSeedService(session).seed_if_empty()
    yield


app = FastAPI(
    title="Vellano API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthContextMiddleware)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(users.users_router)
app.include_router(users.profile_router)
app.include_router(locations.locations_router)
