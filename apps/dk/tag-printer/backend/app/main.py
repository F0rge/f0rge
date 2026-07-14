from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="DasKasas Tag Tool API",
    description="API for generating price tags from DEAR Inventory CSV exports",
    version="2.0.0",
)

_default_origins = ["http://localhost:3000", "http://frontend:3000"]
_env_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _env_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api", tags=["tags"])


@app.get("/")
async def root():
    return {"message": "DasKasas Tag Tool API", "version": "2.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
