from __future__ import annotations

from fastapi import APIRouter, Response

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
