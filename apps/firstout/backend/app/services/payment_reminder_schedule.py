"""Pure schedule and template helpers for invoice payment reminders."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

PDF_NOTE = "The invoice PDF is attached to this email."

PLACEHOLDERS = (
    "customer_name",
    "invoice_number",
    "amount_owing",
    "due_date",
    "days_overdue",
    "invoice_pdf",
)

TERMINAL_STATUSES = frozenset({"sent", "skipped", "sending"})


@dataclass(frozen=True)
class ReminderStep:
    offset_days: int
    subject: str
    body: str


def default_steps() -> list[ReminderStep]:
    return [
        ReminderStep(
            offset_days=-3,
            subject="A quick note about invoice {invoice_number}",
            body=(
                "Hi {customer_name},\n\n"
                "Invoice {invoice_number} for {amount_owing} is due on {due_date}. "
                "This is just a friendly reminder in case it helps.\n\n"
                "{invoice_pdf}\n\n"
                "Thank you."
            ),
        ),
        ReminderStep(
            offset_days=0,
            subject="Invoice {invoice_number} is due today",
            body=(
                "Hi {customer_name},\n\n"
                "Invoice {invoice_number} for {amount_owing} is due today ({due_date}). "
                "The invoice is attached if you need another copy.\n\n"
                "{invoice_pdf}\n\n"
                "Thank you."
            ),
        ),
        ReminderStep(
            offset_days=7,
            subject="Invoice {invoice_number} is now overdue",
            body=(
                "Hi {customer_name},\n\n"
                "Invoice {invoice_number} for {amount_owing} was due on {due_date} "
                "and is now {days_overdue} days overdue. "
                "If you have already paid, you can ignore this note.\n\n"
                "{invoice_pdf}\n\n"
                "Thank you."
            ),
        ),
        ReminderStep(
            offset_days=14,
            subject="Following up on invoice {invoice_number}",
            body=(
                "Hi {customer_name},\n\n"
                "We are following up on invoice {invoice_number} for {amount_owing}. "
                "It was due on {due_date} and is {days_overdue} days overdue. "
                "Please let us know if anything is holding it up.\n\n"
                "{invoice_pdf}\n\n"
                "Thank you."
            ),
        ),
        ReminderStep(
            offset_days=30,
            subject="Invoice {invoice_number} is 30 days overdue",
            body=(
                "Hi {customer_name},\n\n"
                "Invoice {invoice_number} for {amount_owing} was due on {due_date} "
                "and is now {days_overdue} days overdue. "
                "We would appreciate payment, or a note if you need to talk it through.\n\n"
                "{invoice_pdf}\n\n"
                "Thank you."
            ),
        ),
    ]


def steps_from_raw(raw: object) -> list[ReminderStep]:
    """Stored JSON. ``None`` means the built-in schedule. ``[]`` means no steps."""
    if raw is None:
        return default_steps()
    if not isinstance(raw, list):
        return default_steps()
    steps: list[ReminderStep] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        steps.append(
            ReminderStep(
                offset_days=int(item["offset_days"]),
                subject=str(item["subject"]),
                body=str(item["body"]),
            )
        )
    return steps


def steps_to_raw(steps: list[ReminderStep]) -> list[dict[str, object]]:
    return [
        {"offset_days": step.offset_days, "subject": step.subject, "body": step.body}
        for step in steps
    ]


def trigger_on(due: datetime.date, offset_days: int) -> datetime.date:
    return due + datetime.timedelta(days=offset_days)


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def placeholder_values(
    *,
    customer_name: str,
    invoice_number: str,
    amount_owing: str,
    due: datetime.date,
    today: datetime.date,
) -> dict[str, str]:
    return {
        "customer_name": customer_name,
        "invoice_number": invoice_number,
        "amount_owing": amount_owing,
        "due_date": due.strftime("%d %b %Y"),
        "days_overdue": str((today - due).days),
        "invoice_pdf": PDF_NOTE,
    }


def step_to_send(
    due: datetime.date,
    steps: list[ReminderStep],
    today: datetime.date,
    terminal_offsets: set[int],
) -> ReminderStep | None:
    """Latest step whose date has arrived and has not already been sent or skipped.

    Earlier unsent steps are left for the caller to skip, so a customer who is
    already 30 days overdue gets one email, not five.
    """
    ready = [
        step
        for step in steps
        if step.offset_days not in terminal_offsets and trigger_on(due, step.offset_days) <= today
    ]
    if not ready:
        return None
    return max(ready, key=lambda step: step.offset_days)


def superseded_offsets(
    due: datetime.date,
    steps: list[ReminderStep],
    today: datetime.date,
    terminal_offsets: set[int],
    chosen: ReminderStep,
) -> list[int]:
    return [
        step.offset_days
        for step in steps
        if step.offset_days < chosen.offset_days
        and step.offset_days not in terminal_offsets
        and trigger_on(due, step.offset_days) <= today
    ]
