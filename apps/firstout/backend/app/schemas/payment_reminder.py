from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

ReminderRowStatus = Literal[
    "upcoming",
    "due",
    "superseded",
    "sent",
    "skipped",
    "failed",
    "no_email",
    "sending",
    "paused",
    "opted_out",
]


class PaymentReminderStepInput(BaseModel):
    offset_days: int = Field(ge=-365, le=365)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)


class PaymentReminderSettingsResponse(BaseModel):
    enabled: bool
    steps: list[PaymentReminderStepInput]
    last_run_on: Optional[datetime.date] = None
    placeholders: list[str]


class PaymentReminderSettingsUpdate(BaseModel):
    enabled: bool
    steps: list[PaymentReminderStepInput]

    @model_validator(mode="after")
    def unique_offsets(self) -> PaymentReminderSettingsUpdate:
        if len(self.steps) > 12:
            raise ValueError("Use at most 12 reminder steps.")
        offsets = [step.offset_days for step in self.steps]
        if len(offsets) != len(set(offsets)):
            raise ValueError("Each reminder step needs its own day offset.")
        return self


class ReminderRow(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer_name: str
    customer_email: Optional[str] = None
    offset_days: int
    trigger_on: datetime.date
    amount_owing: Decimal
    days_overdue: int
    status: ReminderRowStatus
    sent_at: Optional[datetime.datetime] = None
    detail: Optional[str] = None
    reminders_paused: bool = False
    payment_reminders_opt_out: bool = False


class ReminderAttention(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer_name: str
    reason: Literal["no_email", "no_due_date"]


class ReminderBoard(BaseModel):
    enabled: bool
    upcoming: list[ReminderRow]
    due: list[ReminderRow]
    sent: list[ReminderRow]
    held: list[ReminderRow]
    needs_attention: list[ReminderAttention]


class ReminderActionRequest(BaseModel):
    invoice_id: uuid.UUID
    offset_days: int = Field(ge=-365, le=365)


class ReminderOptOutRequest(BaseModel):
    opt_out: bool


class ReminderOptOutResponse(BaseModel):
    customer_id: uuid.UUID
    payment_reminders_opt_out: bool


class ReminderPauseResponse(BaseModel):
    invoice_id: uuid.UUID
    reminders_paused: bool
