"""Payment reminder schedule, idempotency, and send rules. SMTP is mocked."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.payment_reminder_schedule import (
    default_steps,
    placeholder_values,
    render_template,
    step_to_send,
    superseded_offsets,
)
from app.services.payment_reminders import PaymentReminderService
from app.services.settlement import format_money
from f0rge_db.crud import unit_of_work


@pytest.fixture(autouse=True)
def _reminder_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "settings_encryption_key", Fernet.generate_key().decode())


def test_schedule_sends_only_the_latest_due_step() -> None:
    due = date(2026, 10, 1)
    steps = default_steps()
    today = date(2026, 10, 8)
    chosen = step_to_send(due, steps, today, set())
    assert chosen is not None
    assert chosen.offset_days == 7
    assert superseded_offsets(due, steps, today, set(), chosen) == [-3, 0]


def test_schedule_before_the_due_date_uses_the_early_step() -> None:
    due = date(2026, 10, 10)
    chosen = step_to_send(due, default_steps(), date(2026, 10, 7), set())
    assert chosen is not None
    assert chosen.offset_days == -3
    assert superseded_offsets(due, default_steps(), date(2026, 10, 7), set(), chosen) == []


def test_schedule_does_not_repeat_a_sent_step() -> None:
    due = date(2026, 10, 1)
    chosen = step_to_send(due, default_steps(), date(2026, 11, 5), {-3, 0, 7, 14})
    assert chosen is not None
    assert chosen.offset_days == 30


def test_template_uses_the_outstanding_balance() -> None:
    values = placeholder_values(
        customer_name="Asha",
        invoice_number="INV-0001",
        amount_owing=format_money(Decimal("750.00"), "ZAR"),
        due=date(2026, 10, 1),
        today=date(2026, 10, 8),
    )
    body = render_template(
        "Balance {amount_owing} on {invoice_number} for {customer_name}.", values
    )
    assert body == "Balance R 750.00 on INV-0001 for Asha."
    assert values["days_overdue"] == "7"
    assert "PDF is attached" in values["invoice_pdf"]


async def _configure_smtp(owner_client: AsyncClient) -> None:
    resp = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_username": "shop@example.com",
            "smtp_password": "pw",
            "smtp_from_address": "shop@example.com",
            "smtp_from_name": "Firstout",
        },
    )
    assert resp.status_code == 200


async def _enable_reminders(owner_client: AsyncClient) -> None:
    current = await owner_client.get("/api/v1/settings/payment-reminders")
    assert current.status_code == 200
    body = current.json()
    assert body["enabled"] is False
    saved = await owner_client.patch(
        "/api/v1/settings/payment-reminders",
        json={"enabled": True, "steps": body["steps"]},
    )
    assert saved.status_code == 200
    assert saved.json()["enabled"] is True


async def _create_invoice(
    owner_client: AsyncClient,
    *,
    name: str,
    email: str | None,
) -> dict:
    payload: dict = {"name": name}
    if email is not None:
        payload["email"] = email
    customer = await owner_client.post("/api/v1/customers", json=payload)
    assert customer.status_code == 201
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert invoice.status_code == 201
    body = invoice.json()
    body["customer_id"] = customer.json()["id"]
    return body


def _capture_smtp(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []

    async def fake_send(config, *, to, subject, body_text, pdf_bytes=None, pdf_filename=None):
        sent.append(
            {
                "to": to,
                "subject": subject,
                "body": body_text,
                "pdf": pdf_bytes,
                "filename": pdf_filename,
            }
        )
        return "<reminder-test@example.com>"

    monkeypatch.setattr("app.services.comms.send.send_message", fake_send)
    return sent


async def test_reminders_are_disabled_by_default(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _capture_smtp(monkeypatch)
    await _configure_smtp(owner_client)
    invoice = await _create_invoice(owner_client, name="Quiet Customer", email="quiet@example.com")
    assert invoice["due_date"] == "2026-10-01"
    result = await PaymentReminderService(async_db).tick(today=date(2026, 10, 8))
    assert result["ran"] == 0
    assert sent == []


async def test_reminder_is_idempotent_and_stops_when_paid(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _capture_smtp(monkeypatch)
    await _configure_smtp(owner_client)
    await _enable_reminders(owner_client)
    invoice = await _create_invoice(owner_client, name="Owing Customer", email="owing@example.com")
    service = PaymentReminderService(async_db)

    first = await service.tick(today=date(2026, 10, 8))
    assert first["sent"] == 1
    assert len(sent) == 1
    assert sent[0]["to"] == "owing@example.com"
    assert invoice["invoice_number"] in sent[0]["subject"]
    assert "R 1,150.00" in sent[0]["body"]
    assert sent[0]["pdf"]

    second = await service.tick(today=date(2026, 10, 8))
    assert second["ran"] == 0
    assert len(sent) == 1

    settings_row = await service._team_settings()
    async with unit_of_work(async_db):
        settings_row.payment_reminders_last_run_on = None
    await service.tick(today=date(2026, 10, 8))
    assert len(sent) == 1

    paid = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice["id"],
            "amount": "1150.00",
            "currency": "ZAR",
            "paid_on": "2026-10-08",
        },
    )
    assert paid.status_code == 201
    await service.tick(today=date(2026, 10, 15))
    assert len(sent) == 1


async def test_partial_payment_reminder_shows_the_remaining_balance(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _capture_smtp(monkeypatch)
    await _configure_smtp(owner_client)
    await _enable_reminders(owner_client)
    invoice = await _create_invoice(owner_client, name="Partial Reminder", email="part@example.com")
    paid = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice["id"],
            "amount": "400.00",
            "currency": "ZAR",
            "paid_on": "2026-09-20",
        },
    )
    assert paid.status_code == 201
    result = await PaymentReminderService(async_db).tick(today=date(2026, 10, 8))
    assert result["sent"] == 1
    assert "R 750.00" in sent[0]["body"]
    assert "R 1,150.00" not in sent[0]["body"]


async def test_opt_out_pause_and_missing_email(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _capture_smtp(monkeypatch)
    await _configure_smtp(owner_client)
    await _enable_reminders(owner_client)
    opted = await _create_invoice(owner_client, name="Opt Out Customer", email="opt@example.com")
    paused = await _create_invoice(owner_client, name="Paused Customer", email="pause@example.com")
    silent = await _create_invoice(owner_client, name="No Email Customer", email=None)

    opt = await owner_client.post(
        f"/api/v1/payment-reminders/customers/{opted['customer_id']}/opt-out",
        json={"opt_out": True},
    )
    assert opt.status_code == 200
    assert opt.json()["payment_reminders_opt_out"] is True

    pause = await owner_client.post(f"/api/v1/payment-reminders/invoices/{paused['id']}/pause")
    assert pause.status_code == 200
    assert pause.json()["reminders_paused"] is True

    result = await PaymentReminderService(async_db).tick(today=date(2026, 10, 8))
    assert result["sent"] == 0
    assert sent == []
    assert result["no_email"] == 1

    board = await owner_client.get("/api/v1/payment-reminders")
    assert board.status_code == 200
    body = board.json()
    reasons = {item["invoice_number"]: item["reason"] for item in body["needs_attention"]}
    assert reasons[silent["invoice_number"]] == "no_email"
    held_statuses = {row["invoice_number"]: row["status"] for row in body["held"]}
    assert held_statuses[opted["invoice_number"]] == "opted_out"
    assert held_statuses[paused["invoice_number"]] == "paused"

    skipped = await owner_client.post(
        "/api/v1/payment-reminders/skip",
        json={"invoice_id": paused["id"], "offset_days": 7},
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    resume = await owner_client.post(f"/api/v1/payment-reminders/invoices/{paused['id']}/resume")
    assert resume.status_code == 200
    detail = await owner_client.get(f"/api/v1/invoices/{paused['id']}")
    assert detail.json()["reminders_paused"] is False
