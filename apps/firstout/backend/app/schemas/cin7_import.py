from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Cin7EntityCounts(BaseModel):
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0


class Cin7ImportSummary(BaseModel):
    entities: dict[str, Cin7EntityCounts] = Field(default_factory=dict)
    price_changes: dict[str, int] = Field(default_factory=dict)
    generated_barcodes: int = 0
    generated_barcodes_blank: int = 0
    generated_barcodes_shared: int = 0


class Cin7ImportRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    finished_at: Optional[datetime.datetime]
    user_id: uuid.UUID
    user_email: str
    file_sha256: str
    file_name: str
    mode: str
    status: str
    dry_run_id: Optional[uuid.UUID]
    summary: Cin7ImportSummary
    warning_count: int
    error_count: int


class Cin7ImportCommitRequest(BaseModel):
    file_sha256: str = Field(min_length=64, max_length=64)
