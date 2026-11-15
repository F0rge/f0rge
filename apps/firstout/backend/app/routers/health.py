from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.services.release_readiness import release_readiness

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_class=JSONResponse)
async def ready() -> JSONResponse:
    return await release_readiness()
