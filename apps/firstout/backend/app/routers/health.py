from __future__ import annotations

from fastapi import APIRouter, Response
from starlette.responses import JSONResponse

from app.services.release_readiness import release_readiness

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}


@router.get("/ready", response_class=JSONResponse)
async def ready() -> JSONResponse:
    return await release_readiness()
