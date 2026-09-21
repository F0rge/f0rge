from __future__ import annotations

from app.config import settings
from app.schemas.nia import NiaHealthResponse


class NiaHealthService:
    def health(self) -> NiaHealthResponse:
        return NiaHealthResponse(ok=True, llm=bool(settings.openrouter_api_key))
