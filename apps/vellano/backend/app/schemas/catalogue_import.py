from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CatalogueImportRowError(BaseModel):
    file: Literal["inventory", "soh"]
    row: int
    message: str


class CatalogueImportFilePreview(BaseModel):
    headers: list[str]
    suggested_map: dict[str, str]
    applied_map: dict[str, str]
    sample_row: dict[str, str]
    row_count: int
    create_count: int = 0
    update_count: int = 0


class CatalogueImportSohPreview(BaseModel):
    headers: list[str]
    suggested_map: dict[str, str]
    applied_map: dict[str, str]
    sample_row: dict[str, str]
    row_count: int


class CatalogueImportPreviewResponse(BaseModel):
    ok: bool
    errors: list[CatalogueImportRowError] = Field(default_factory=list)
    inventory: CatalogueImportFilePreview
    soh: Optional[CatalogueImportSohPreview] = None


class CatalogueImportCommitResponse(BaseModel):
    created_skus: int
    updated_skus: int
    soh_rows: int
