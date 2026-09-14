from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class CommsMessageResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    sent_at: Optional[datetime.datetime] = None
    channel: str
    provider: str
    document_type: str
    document_id: uuid.UUID
    to_address: str
    from_identity: str
    status: str
    provider_message_id: Optional[str] = None
    error: Optional[str] = None


class CommsSettingsResponse(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_security: str = "starttls"
    smtp_username: Optional[str] = None
    smtp_from_address: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_reply_to: Optional[str] = None
    smtp_configured: bool = False
    has_smtp_password: bool = False


class CommsSettingsUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(default=None, ge=1, le=65535)
    smtp_security: Optional[str] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_address: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_reply_to: Optional[str] = None


class CommsTestEmailRequest(BaseModel):
    to: EmailStr


class CommsTestEmailResponse(BaseModel):
    ok: bool
