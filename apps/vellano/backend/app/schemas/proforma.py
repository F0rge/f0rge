from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class ProformaResponse(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    invoice_number: str
    invoice_date: datetime.date
    currency: str
    pdf_storage_key: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
