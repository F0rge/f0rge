from __future__ import annotations

from typing import Generic, Optional, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)


class PageParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    q: Optional[str] = None


def get_page_params(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
) -> PageParams:
    cleaned = q.strip() if q else None
    return PageParams(limit=limit, offset=offset, q=cleaned or None)
