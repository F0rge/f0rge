from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class TeamBrief(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)
