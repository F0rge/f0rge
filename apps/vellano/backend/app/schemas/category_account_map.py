from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CategoryAccountMapUpsert(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    sales_code: str = Field(min_length=1, max_length=16)
    cogs_code: str = Field(min_length=1, max_length=16)
    stock_adj_code: str = Field(min_length=1, max_length=16)
    count_var_code: str = Field(min_length=1, max_length=16)


class CategoryAccountMapResponse(BaseModel):
    id: uuid.UUID
    category: str
    sales_code: str
    cogs_code: str
    stock_adj_code: str
    count_var_code: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
