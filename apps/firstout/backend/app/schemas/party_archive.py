from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PartyArchiveUpdate(BaseModel):
    is_archived: bool

    model_config = ConfigDict(extra="forbid")


class PartyArchiveCounts(BaseModel):
    active: int = Field(ge=0)
    archived: int = Field(ge=0)
