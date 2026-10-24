"""Send and list invoice payment reminders. Email only, at most once a day."""

from __future__ import annotations

import datetime
import logging
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.customer import Customer
from app.models.payment_reminder import PaymentReminderSend
from app.models.tax_invoice import TaxInvoice
from app.schemas.payment_reminder import (
    PaymentReminderSettingsResponse,
    PaymentReminderSettingsUpdate,
    PaymentReminderStepInput,
    ReminderActionRequest,
    ReminderAttention,
    ReminderBoard,
    ReminderOptOutResponse,
    ReminderPauseResponse,
    ReminderRow,
)
from app.services.comms.send import CommsSendService
from app.services.payment_terms import invoice_collectible_balance, invoice_open_balance_expr
from app.services.payment_reminder_schedule import (
    PLACEHOLDERS,
    TERMINAL_STATUSES,
    ReminderStep,
    placeholder_values,
    render_template,
    step_to_send,
    steps_from_raw,
    steps_to_raw,
    superseded_offsets,
    trigger_on,
)
from app.services.settlement import cents, format_money
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

logger = logging.getLogger(__name__)

_SKIP_LATER = "A later reminder covers this invoice."


def _amount_owing(invoice: TaxInvoice) -> Decimal:
    return cents(invoice_collectible_balance(invoice))


class PaymentReminderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.comms = CommsSendService(db)
        self.settings_crud = TeamSettingsCRUD(db)
        self.team_crud = TeamCRUD(db)

    async def get_settings(self) -> PaymentReminderSettingsResponse:
        settings = await self._team_settings()
        return self._settings_response(settings)

    async def update_settings(
        self, data: PaymentReminderSettingsUpdate
    ) -> PaymentReminderSettingsResponse:
        settings = await self._team_settings()
        stored = [
            ReminderStep(offset_days=step.offset_days, subject=step.subject, body=step.body)
            for step in data.steps
        ]
        async with unit_of_work(self.db):
            settings.payment_reminders_enabled = data.enabled
            settings.payment_reminder_steps = steps_to_raw(stored) if data.steps else []
        return self._settings_response(settings)

    async def board(self, today: Optional[datetime.date] = None) -> ReminderBoard:
        today = today or datetime.date.today()
        settings = await self._team_settings()
        steps = steps_from_raw(settings.payment_reminder_steps)
        invoices = await self._invoices_for_board()
        sends = await self._all_sends()
        by_invoice: dict[uuid.UUID, dict[int, PaymentReminderSend]] = {}
        for row in sends:
            by_invoice.setdefault(row.invoice_id, {})[row.offset_days] = row

        upcoming: list[ReminderRow] = []
        due: list[ReminderRow] = []
        sent: list[ReminderRow] = []
        held: list[ReminderRow] = []
        attention: list[ReminderAttention] = []

        for invoice in invoices:
            customer = invoice.customer
            remaining = _amount_owing(invoice)
            recorded = by_invoice.get(invoice.id, {})
            if remaining <= 0:
                sent.extend(self._recorded_rows(invoice, recorded, today))
                continue
            if invoice.due_date is None:
                attention.append(
                    ReminderAttention(
                        invoice_id=invoice.id,
                        invoice_number=invoice.invoice_number,
                        customer_id=customer.id,
                        customer_name=customer.name,
                        reason="no_due_date",
                    )
                )
                continue
            if not (customer.email or "").strip():
                attention.append(
                    ReminderAttention(
                        invoice_id=invoice.id,
                        invoice_number=invoice.invoice_number,
                        customer_id=customer.id,
                        customer_name=customer.name,
                        reason="no_email",
                    )
                )
            if customer.payment_reminders_opt_out or invoice.reminders_paused:
                held.append(self._held_row(invoice, steps, today, remaining))
                sent.extend(self._recorded_rows(invoice, recorded, today))
                continue

            terminal = {
                offset
                for offset, row in recorded.items()
                if row.status in TERMINAL_STATUSES or row.status == "skipped"
            }
            # skipped is already in TERMINAL_STATUSES
            chosen = step_to_send(invoice.due_date, steps, today, terminal)
            superseded = (
                set(superseded_offsets(invoice.due_date, steps, today, terminal, chosen))
                if chosen is not None
                else set()
            )
            for step in steps:
                existing = recorded.get(step.offset_days)
                if existing is not None and existing.status in {
                    "sent",
                    "skipped",
                    "failed",
                    "no_email",
                    "sending",
                }:
                    sent.append(self._row_from_send(invoice, existing, today))
                    continue
                when = trigger_on(invoice.due_date, step.offset_days)
                if chosen is not None and step.offset_days == chosen.offset_days:
                    status = "no_email" if not (customer.email or "").strip() else "due"
                    due.append(self._open_row(invoice, step, today, remaining, status, detail=None))
                elif step.offset_days in superseded:
                    due.append(
                        self._open_row(
                            invoice,
                            step,
                            today,
                            remaining,
                            "superseded",
                            detail=_SKIP_LATER,
                        )
                    )
                elif when > today:
                    upcoming.append(
                        self._open_row(invoice, step, today, remaining, "upcoming", detail=None)
                    )

        def _sort(rows: list[ReminderRow]) -> list[ReminderRow]:
            return sorted(
                rows, key=lambda row: (row.trigger_on, row.invoice_number, row.offset_days)
            )

        return ReminderBoard(
            enabled=bool(settings.payment_reminders_enabled),
            upcoming=_sort(upcoming),
            due=_sort(due),
            sent=_sort(sent),
            held=held,
            needs_attention=attention,
        )

    async def tick(self, today: Optional[datetime.date] = None) -> dict[str, int]:
        today = today or datetime.date.today()
        settings = await self._team_settings()
        if not settings.payment_reminders_enabled:
            return {"ran": 0, "sent": 0, "skipped": 0, "no_email": 0, "failed": 0}
        if settings.payment_reminders_last_run_on == today:
            return {"ran": 0, "sent": 0, "skipped": 0, "no_email": 0, "failed": 0}

        steps = steps_from_raw(settings.payment_reminder_steps)
        async with unit_of_work(self.db):
            settings.payment_reminders_last_run_on = today

        counts = {"ran": 1, "sent": 0, "skipped": 0, "no_email": 0, "failed": 0}
        invoices = await self._open_invoices()
        for invoice in invoices:
            try:
                outcome = await self._send_due_step(invoice.id, steps, today, actor_user_id=None)
            except Exception:
                logger.exception("payment reminder failed for invoice %s", invoice.id)
                counts["failed"] += 1
                continue
            if outcome in counts:
                counts[outcome] += 1
        return counts

    async def send_now(self, data: ReminderActionRequest, actor_user_id: uuid.UUID) -> ReminderRow:
        invoice = await self._require_invoice(data.invoice_id)
        steps = steps_from_raw((await self._team_settings()).payment_reminder_steps)
        step = self._require_step(steps, data.offset_days)
        outcome = await self._deliver(
            invoice,
            step,
            datetime.date.today(),
            actor_user_id=actor_user_id,
            force=True,
        )
        if outcome == "paid":
            raise ValidationError("Invoice is already fully paid")
        if outcome == "opted_out":
            raise ValidationError("This customer has opted out of payment reminders.")
        if outcome == "paused":
            raise ValidationError("Reminders are paused for this invoice.")
        if outcome == "no_email":
            raise ConflictError("Customer has no email")
        if outcome == "already":
            raise ValidationError("This reminder was already sent or skipped.")
        if outcome == "failed":
            raise ValidationError("The reminder email could not be sent.")
        recorded = await self._find_send(invoice.id, step.offset_days)
        assert recorded is not None
        return self._row_from_send(invoice, recorded, datetime.date.today())

    async def skip(self, data: ReminderActionRequest, actor_user_id: uuid.UUID) -> ReminderRow:
        invoice = await self._require_invoice(data.invoice_id)
        if invoice.due_date is None:
            raise ValidationError("This invoice has no due date.")
        existing = await self._find_send(invoice.id, data.offset_days)
        if existing is not None and existing.status == "sent":
            raise ValidationError("This reminder was already sent.")
        if existing is not None and existing.status == "skipped":
            return self._row_from_send(invoice, existing, datetime.date.today())
        remaining = _amount_owing(invoice)
        row = await self._upsert_send(
            invoice_id=invoice.id,
            offset_days=data.offset_days,
            status="skipped",
            amount_owing=remaining,
            error=None,
            actor_user_id=actor_user_id,
            sent_at=datetime.datetime.utcnow(),
        )
        return self._row_from_send(invoice, row, datetime.date.today())

    async def set_paused(self, invoice_id: uuid.UUID, paused: bool) -> ReminderPauseResponse:
        invoice = await self._require_invoice(invoice_id)
        async with unit_of_work(self.db):
            invoice.reminders_paused = paused
        return ReminderPauseResponse(invoice_id=invoice.id, reminders_paused=paused)

    async def set_opt_out(self, customer_id: uuid.UUID, opt_out: bool) -> ReminderOptOutResponse:
        customer = await self.db.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        async with unit_of_work(self.db):
            customer.payment_reminders_opt_out = opt_out
        return ReminderOptOutResponse(
            customer_id=customer.id,
            payment_reminders_opt_out=opt_out,
        )

    async def _send_due_step(
        self,
        invoice_id: uuid.UUID,
        steps: list[ReminderStep],
        today: datetime.date,
        actor_user_id: Optional[uuid.UUID],
    ) -> str:
        invoice = await self._require_invoice(invoice_id)
        if invoice.due_date is None or invoice.is_archive:
            return "ignored"
        remaining = _amount_owing(invoice)
        if remaining <= 0:
            return "paid"
        if invoice.customer.payment_reminders_opt_out or invoice.reminders_paused:
            return "held"
        sends = await self._sends_for_invoice(invoice.id)
        terminal = {row.offset_days for row in sends if row.status in TERMINAL_STATUSES}
        chosen = step_to_send(invoice.due_date, steps, today, terminal)
        if chosen is None:
            return "ignored"
        for offset in superseded_offsets(invoice.due_date, steps, today, terminal, chosen):
            await self._upsert_send(
                invoice_id=invoice.id,
                offset_days=offset,
                status="skipped",
                amount_owing=remaining,
                error=_SKIP_LATER,
                actor_user_id=actor_user_id,
                sent_at=datetime.datetime.utcnow(),
            )
        return await self._deliver(invoice, chosen, today, actor_user_id=actor_user_id, force=False)

    async def _deliver(
        self,
        invoice: TaxInvoice,
        step: ReminderStep,
        today: datetime.date,
        *,
        actor_user_id: Optional[uuid.UUID],
        force: bool,
    ) -> str:
        invoice = await self._require_invoice(invoice.id)
        remaining = _amount_owing(invoice)
        if remaining <= 0:
            return "paid"
        if invoice.customer.payment_reminders_opt_out:
            return "opted_out"
        if invoice.reminders_paused:
            return "paused"
        if invoice.due_date is None:
            raise ValidationError("This invoice has no due date.")
        existing = await self._find_send(invoice.id, step.offset_days)
        if existing is not None and existing.status in TERMINAL_STATUSES:
            return "already"
        email = (invoice.customer.email or "").strip()
        if not email:
            await self._upsert_send(
                invoice_id=invoice.id,
                offset_days=step.offset_days,
                status="no_email",
                amount_owing=remaining,
                error="Customer has no email",
                actor_user_id=actor_user_id,
                sent_at=None,
            )
            return "no_email"
        if not force and trigger_on(invoice.due_date, step.offset_days) > today:
            return "ignored"

        values = placeholder_values(
            customer_name=invoice.customer.name,
            invoice_number=invoice.invoice_number,
            amount_owing=format_money(remaining, "ZAR"),
            due=invoice.due_date,
            today=today,
        )
        subject = render_template(step.subject, values)
        body = render_template(step.body, values)
        await self._upsert_send(
            invoice_id=invoice.id,
            offset_days=step.offset_days,
            status="sending",
            amount_owing=remaining,
            error=None,
            actor_user_id=actor_user_id,
            sent_at=None,
        )
        try:
            message_id = await self.comms.send_payment_reminder(
                invoice_id=invoice.id,
                to_address=email,
                subject=subject,
                body_text=body,
                actor_user_id=actor_user_id,
            )
        except (ConflictError, NotFoundError) as exc:
            detail = exc.detail
            await self._upsert_send(
                invoice_id=invoice.id,
                offset_days=step.offset_days,
                status="failed",
                amount_owing=remaining,
                error=str(detail)[:2000],
                actor_user_id=actor_user_id,
                sent_at=None,
            )
            return "failed"
        await self._upsert_send(
            invoice_id=invoice.id,
            offset_days=step.offset_days,
            status="sent",
            amount_owing=remaining,
            error=None,
            actor_user_id=actor_user_id,
            sent_at=datetime.datetime.utcnow(),
            comms_message_id=message_id,
        )
        return "sent"

    async def _upsert_send(
        self,
        *,
        invoice_id: uuid.UUID,
        offset_days: int,
        status: str,
        amount_owing: Decimal,
        error: Optional[str],
        actor_user_id: Optional[uuid.UUID],
        sent_at: Optional[datetime.datetime],
        comms_message_id: Optional[uuid.UUID] = None,
    ) -> PaymentReminderSend:
        row = await self._find_send(invoice_id, offset_days)
        async with unit_of_work(self.db):
            if row is None:
                row = PaymentReminderSend(
                    invoice_id=invoice_id,
                    offset_days=offset_days,
                    status=status,
                    amount_owing=amount_owing,
                    error=error,
                    actor_user_id=actor_user_id,
                    sent_at=sent_at,
                    comms_message_id=comms_message_id,
                )
                self.db.add(row)
            else:
                row.status = status
                row.amount_owing = amount_owing
                row.error = error
                row.actor_user_id = actor_user_id
                row.sent_at = sent_at
                if comms_message_id is not None:
                    row.comms_message_id = comms_message_id
            await self.db.flush()
        return row

    async def _find_send(
        self, invoice_id: uuid.UUID, offset_days: int
    ) -> Optional[PaymentReminderSend]:
        result = await self.db.execute(
            select(PaymentReminderSend).where(
                PaymentReminderSend.invoice_id == invoice_id,
                PaymentReminderSend.offset_days == offset_days,
            )
        )
        return result.scalar_one_or_none()

    async def _sends_for_invoice(self, invoice_id: uuid.UUID) -> list[PaymentReminderSend]:
        result = await self.db.execute(
            select(PaymentReminderSend).where(PaymentReminderSend.invoice_id == invoice_id)
        )
        return list(result.scalars().all())

    async def _all_sends(self) -> list[PaymentReminderSend]:
        result = await self.db.execute(select(PaymentReminderSend))
        return list(result.scalars().all())

    async def _open_invoices(self) -> list[TaxInvoice]:
        result = await self.db.execute(
            select(TaxInvoice)
            .options(
                selectinload(TaxInvoice.customer),
                selectinload(TaxInvoice.credit_note),
            )
            .where(TaxInvoice.is_archive.is_(False))
            .where(invoice_open_balance_expr() > 0)
        )
        return list(result.scalars().all())

    async def _invoices_for_board(self) -> list[TaxInvoice]:
        result = await self.db.execute(
            select(TaxInvoice)
            .options(
                selectinload(TaxInvoice.customer),
                selectinload(TaxInvoice.credit_note),
            )
            .where(TaxInvoice.is_archive.is_(False))
        )
        return list(result.scalars().all())

    async def _require_invoice(self, invoice_id: uuid.UUID) -> TaxInvoice:
        result = await self.db.execute(
            select(TaxInvoice)
            .options(
                selectinload(TaxInvoice.customer),
                selectinload(TaxInvoice.lines),
                selectinload(TaxInvoice.credit_note),
            )
            .where(TaxInvoice.id == invoice_id)
            .execution_options(populate_existing=True)
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise NotFoundError("Invoice not found")
        return invoice

    async def _team_settings(self):
        team = await self.team_crud.get_first()
        if team is None:
            raise NotFoundError("Team not found")
        return await self.settings_crud.get_or_create_for_team(team.id)

    @staticmethod
    def _require_step(steps: list[ReminderStep], offset_days: int) -> ReminderStep:
        for step in steps:
            if step.offset_days == offset_days:
                return step
        raise ValidationError("That reminder step is not on the schedule.")

    @staticmethod
    def _settings_response(settings) -> PaymentReminderSettingsResponse:
        steps = steps_from_raw(settings.payment_reminder_steps)
        return PaymentReminderSettingsResponse(
            enabled=bool(settings.payment_reminders_enabled),
            steps=[
                PaymentReminderStepInput(
                    offset_days=step.offset_days,
                    subject=step.subject,
                    body=step.body,
                )
                for step in steps
            ],
            last_run_on=settings.payment_reminders_last_run_on,
            placeholders=list(PLACEHOLDERS),
        )

    def _open_row(
        self,
        invoice: TaxInvoice,
        step: ReminderStep,
        today: datetime.date,
        remaining: Decimal,
        status: str,
        detail: Optional[str],
    ) -> ReminderRow:
        assert invoice.due_date is not None
        return ReminderRow(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.name,
            customer_email=(invoice.customer.email or "").strip() or None,
            offset_days=step.offset_days,
            trigger_on=trigger_on(invoice.due_date, step.offset_days),
            amount_owing=remaining,
            days_overdue=(today - invoice.due_date).days,
            status=status,  # type: ignore[arg-type]
            detail=detail,
            reminders_paused=invoice.reminders_paused,
            payment_reminders_opt_out=invoice.customer.payment_reminders_opt_out,
        )

    def _row_from_send(
        self, invoice: TaxInvoice, row: PaymentReminderSend, today: datetime.date
    ) -> ReminderRow:
        due = invoice.due_date or invoice.issue_date
        return ReminderRow(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.name,
            customer_email=(invoice.customer.email or "").strip() or None,
            offset_days=row.offset_days,
            trigger_on=trigger_on(due, row.offset_days),
            amount_owing=row.amount_owing,
            days_overdue=(today - due).days,
            status=row.status,  # type: ignore[arg-type]
            sent_at=row.sent_at,
            detail=row.error,
            reminders_paused=invoice.reminders_paused,
            payment_reminders_opt_out=invoice.customer.payment_reminders_opt_out,
        )

    def _recorded_rows(
        self,
        invoice: TaxInvoice,
        recorded: dict[int, PaymentReminderSend],
        today: datetime.date,
    ) -> list[ReminderRow]:
        return [self._row_from_send(invoice, row, today) for row in recorded.values()]

    def _held_row(
        self,
        invoice: TaxInvoice,
        steps: list[ReminderStep],
        today: datetime.date,
        remaining: Decimal,
    ) -> ReminderRow:
        assert invoice.due_date is not None
        step = steps[0] if steps else ReminderStep(0, "", "")
        status = "opted_out" if invoice.customer.payment_reminders_opt_out else "paused"
        return self._open_row(invoice, step, today, remaining, status, detail=None)
