from __future__ import annotations

from pydantic import BaseModel


class NiaHealthResponse(BaseModel):
    ok: bool
    llm: bool
