from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FeatureMatrixPage(BaseModel):
    data: list[dict[str, Any]]
    columns: list[str]
    total: int
    page: int
    size: int
    pages: int
