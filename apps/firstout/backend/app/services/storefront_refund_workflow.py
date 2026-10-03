from __future__ import annotations

import datetime
import hashlib
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.credit_note import CreditNote
from app.models.journal import JournalDocumentType
from app.models.ops_commerce_order import OpsCommerceOrder
from app.models.ops_commerce_refund import OpsCommerceRefund, OpsCommerceRefundEvent
from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderStatus
from app.models.stock_return import StockReturn, StockReturnStatus
from app.models.user import User
from app.schemas.ops_commerce_order import (
    StorefrontRefundCommand,
    StorefrontRefundCommandList,
    StorefrontRefundDispatchOutcome,
    StorefrontRefundLineBalance,
    StorefrontRefundProviderEvent,
    StorefrontRefundProviderEventResponse,
    StorefrontRefundRequest,
    StorefrontRefundResponse,
    StorefrontRefundStatusResponse,
)
from app.services.books_periods import assert_date_postable
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_DEPOSITS,
    CODE_STOREFRONT_CLEARING,
    LedgerPostingService,
)
from app.services.ops_commerce import OpsCommerceService
from app.services.sales_orders import SalesOrdersService
from app.services.storefront_fulfillment import StorefrontFulfillmentService
from app.services.storefront_refunds import (
    allocate_refund_cents,
    allocate_selected_line_refund,
    storefront_line_values,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

CENT = Decimal("0.01")
OPEN_REFUND_STATES = ("requested", "dispatching", "unknown", "pending", "needs_review")
COMMITTED_REFUND_STATES = (*OPEN_REFUND_STATES, "succeeded")
DISPATCHABLE_STATES = ("requested", "dispatching")


class StorefrontRefundWorkflowService:
    """Own staff refund commands, verified Peach outcomes, and Firstout convergence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.posting = LedgerPostingService(db)

    async def request_refund_for_staff(
        self,
        handoff_id: uuid.UUID,
        request: StorefrontRefundRequest,
        staff_user_id: uuid.UUID,
    ) -> StorefrontRefundResponse:
        company_id = OpsCommerceService._configured_company_id()
        return await self.request_refund(handoff_id, request, staff_user_id, company_id)

    async def get_status_for_staff(
        self, handoff_id: uuid.UUID, staff_user_id: uuid.UUID
    ) -> StorefrontRefundStatusResponse:
        company_id = OpsCommerceService._configured_company_id()
        return await self.get_status(handoff_id, staff_user_id, company_id)

    async def request_refund(
        self,
        handoff_id: uuid.UUID,
        request: StorefrontRefundRequest,
        staff_user_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> StorefrontRefundResponse:
        selected = (
            {line.external_line_id: line.quantity for line in request.selected_lines}
            if request.selected_lines is not None
            else {}
        )
        async with unit_of_work(self.db):
            handoff = await self._handoff(handoff_id, company_id, for_update=True)
            await self._require_company_staff(staff_user_id, company_id)
            duplicate = await self.db.scalar(
                select(OpsCommerceRefund)
                .where(
                    OpsCommerceRefund.handoff_id == handoff_id,
                    OpsCommerceRefund.idempotency_key == str(request.idempotency_key),
                )
                .with_for_update()
            )
            if duplicate is not None:
                if (
                    duplicate.selected_lines != selected
                    or duplicate.cancel_order != request.cancel_order
                    or (not selected and duplicate.amount_minor != request.amount_minor)
                ):
                    raise ConflictError("Refund idempotency key was reused with different details")
                return self._refund_response(duplicate)

            order = await self._sales_order(handoff.sales_order_id, for_update=True)
            self._assert_refund_eligible(handoff, order)
            if order.invoice_id is not None and order.status != SalesOrderStatus.INVOICED:
                raise ConflictError("Storefront invoiced order is not eligible for refund")
            credit_note = await self._refund_credit_note_for_order(handoff, order, for_update=True)
            captured = handoff.captured_amount_minor
            snapshot_total = handoff.payload.get("totals", {}).get("total_minor_zar")
            if snapshot_total != captured:
                raise ConflictError(
                    "Storefront capture does not match its immutable order snapshot"
                )

            committed = await self._committed_refunds(handoff_id)
            if any(row.status == "needs_review" for row in committed):
                raise ConflictError(
                    "Resolve the existing Storefront refund review before continuing"
                )
            already_exposed = sum(self._refund_exposure(row) for row in committed)
            available = captured - already_exposed
            if order.invoice_id is not None:
                if request.cancel_order:
                    raise ConflictError(
                        "An invoiced Storefront order cannot be cancelled by refund"
                    )
                if request.selected_lines is not None:
                    raise ConflictError("Post-invoice Storefront refunds are amount-only")
                if credit_note is None:
                    raise ConflictError(
                        "Storefront refund after invoicing requires a completed accepted return and credit note"
                    )
                credit_note_cap = self._money_to_minor(credit_note.total_inc_vat)
                available = min(available, credit_note_cap - already_exposed)
            already_allocated = self._sum_allocations(committed)
            already_selected = self._sum_selected_lines(committed)
            if request.amount_minor is not None:
                amount_minor = request.amount_minor
                allocation = allocate_refund_cents(handoff.payload, amount_minor, already_allocated)
            else:
                amount_minor, allocation = allocate_selected_line_refund(
                    handoff.payload,
                    selected,
                    already_allocated,
                    already_selected,
                )
            if amount_minor > available:
                raise ValidationError("Refund amount exceeds the remaining refundable balance")
            if request.cancel_order and amount_minor != available:
                raise ValidationError(
                    "Cancelling the Storefront order requires refunding its full remaining balance"
                )
            if request.cancel_order and any(row.status in OPEN_REFUND_STATES for row in committed):
                raise ConflictError(
                    "Resolve the existing Storefront refund before cancelling the order"
                )

            refund = OpsCommerceRefund(
                id=uuid.uuid4(),
                company_id=company_id,
                handoff_id=handoff_id,
                sales_order_id=order.id,
                requested_by_user_id=staff_user_id,
                request_origin="staff",
                idempotency_key=str(request.idempotency_key),
                amount_minor=amount_minor,
                currency_code=handoff.currency_code,
                allocation=allocation,
                selected_lines=selected,
                cancel_order=request.cancel_order,
                status="requested",
                signature_verified=False,
            )
            self.db.add(refund)
            await self.db.flush()
            return self._refund_response(refund)

    async def get_status(
        self, handoff_id: uuid.UUID, staff_user_id: uuid.UUID, company_id: uuid.UUID
    ) -> StorefrontRefundStatusResponse:
        handoff = await self._handoff(handoff_id, company_id)
        await self._require_company_staff(staff_user_id, company_id)
        order = await self._sales_order(handoff.sales_order_id)
        refunds = list(
            (
                await self.db.scalars(
                    select(OpsCommerceRefund)
                    .where(OpsCommerceRefund.handoff_id == handoff_id)
                    .order_by(OpsCommerceRefund.created_at, OpsCommerceRefund.id)
                )
            ).all()
        )
        confirmed = sum(
            self._effective_amount(row)
            for row in refunds
            if row.provider_outcome == "succeeded" or row.status == "succeeded"
        )
        reserved = sum(
            self._effective_reservation(row) for row in refunds if row.status in OPEN_REFUND_STATES
        )
        committed = [row for row in refunds if row.status in COMMITTED_REFUND_STATES]
        allocated_by_line = self._sum_allocations(committed)
        selected_by_line = self._sum_selected_lines(committed)
        snapshot_values, snapshot_quantities = storefront_line_values(handoff.payload)
        line_snapshots = {
            line["external_line_id"]: line for line in handoff.payload.get("lines", [])
        }
        line_balances = [
            StorefrontRefundLineBalance(
                external_line_id=line_id,
                title=line_snapshots[line_id]["title"],
                sku=line_snapshots[line_id]["sku"],
                original_quantity=quantity,
                remaining_quantity=max(0, quantity - selected_by_line.get(line_id, 0)),
                original_amount_minor=snapshot_values[line_id],
                remaining_amount_minor=max(
                    0, snapshot_values[line_id] - allocated_by_line.get(line_id, 0)
                ),
            )
            for line_id, quantity in snapshot_quantities.items()
        ]
        captured = handoff.captured_amount_minor
        credit_note = await self._refund_credit_note_for_order(handoff, order)
        invoice_available = 0
        if credit_note is not None:
            invoice_available = max(
                0,
                min(
                    captured - sum(self._refund_exposure(row) for row in committed),
                    self._money_to_minor(credit_note.total_inc_vat)
                    - sum(self._refund_exposure(row) for row in committed),
                ),
            )
        return StorefrontRefundStatusResponse(
            captured_amount_minor=captured,
            confirmed_refund_minor=confirmed,
            reserved_refund_minor=reserved,
            available_refund_minor=max(0, captured - confirmed - reserved),
            invoice_id=order.invoice_id,
            invoice_refund_eligible=credit_note is not None,
            invoice_refund_available_minor=invoice_available,
            sales_order_amount_paid=str(order.amount_paid),
            line_balances=line_balances,
            items=[self._refund_response(row) for row in refunds],
        )

    async def list_machine_refund_commands(
        self,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
        limit: int,
    ) -> StorefrontRefundCommandList:
        company_id = await self._authorize_machine(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )
        rows = list(
            (
                await self.db.scalars(
                    select(OpsCommerceRefund)
                    .where(
                        OpsCommerceRefund.company_id == company_id,
                        OpsCommerceRefund.request_origin == "staff",
                        OpsCommerceRefund.status.in_(DISPATCHABLE_STATES),
                    )
                    .order_by(OpsCommerceRefund.created_at, OpsCommerceRefund.id)
                    .limit(limit)
                )
            ).all()
        )
        commands: list[StorefrontRefundCommand] = []
        for refund in rows:
            if refund.handoff_id is None:
                continue
            handoff = await self._handoff(refund.handoff_id, company_id)
            commands.append(
                StorefrontRefundCommand(
                    request_id=refund.id,
                    handoff_id=handoff.id,
                    external_order_id=handoff.external_order_id,
                    original_transaction_id=handoff.gateway_reference,
                    amount_minor=refund.amount_minor,
                    currency_code=refund.currency_code,
                    cancel_order=refund.cancel_order,
                    allocation=refund.allocation,
                    status=refund.status,
                )
            )
        return StorefrontRefundCommandList(items=commands)

    async def record_machine_dispatch_outcome(
        self,
        refund_id: uuid.UUID,
        outcome: StorefrontRefundDispatchOutcome,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> StorefrontRefundResponse:
        company_id = await self._authorize_machine(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )
        return await self.record_dispatch_outcome(refund_id, outcome, company_id)

    async def record_dispatch_outcome(
        self,
        refund_id: uuid.UUID,
        outcome: StorefrontRefundDispatchOutcome,
        company_id: uuid.UUID,
    ) -> StorefrontRefundResponse:
        async with unit_of_work(self.db):
            candidate = await self._refund(refund_id, company_id)
            if candidate.handoff_id is None:
                raise ConflictError("Provider reconciliation record cannot be dispatched")
            await self._handoff(candidate.handoff_id, company_id, for_update=True)
            refund = await self._refund(refund_id, company_id, for_update=True)
            if refund.status in ("succeeded", "failed", "needs_review"):
                return self._refund_response(refund)
            rank = {"requested": 0, "dispatching": 1, "unknown": 2, "pending": 3}
            if rank[outcome.status] > rank[refund.status]:
                refund.status = outcome.status
            if outcome.failure_code is not None:
                refund.failure_code = outcome.failure_code
            return self._refund_response(refund)

    async def record_machine_provider_event(
        self,
        event: StorefrontRefundProviderEvent,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> StorefrontRefundProviderEventResponse:
        company_id = await self._authorize_machine(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )
        return await self.record_provider_event(event, company_id)

    async def record_provider_event(
        self,
        event: StorefrontRefundProviderEvent,
        company_id: uuid.UUID,
    ) -> StorefrontRefundProviderEventResponse:
        if not event.signature_verified:
            raise ValidationError("Peach refund event has not been signature verified")
        if event.event_source == "webhook" and not event.webhook_id:
            raise ValidationError("Signed Peach refund webhook ID is required")
        event_key = (
            f"webhook:{event.webhook_id}"
            if event.event_source == "webhook"
            else f"response:{event.provider_refund_id}:{event.canonical_sha256}"
        )
        existing_event = await self._event_by_identity(
            event_key, event.webhook_id, event.canonical_sha256
        )
        if existing_event is not None:
            if existing_event.company_id != company_id:
                raise ConflictError("Peach refund event ID is already linked to another company")
            return await self._event_response(existing_event, duplicate=True)

        requested_refund = (
            await self._refund(event.request_id, company_id)
            if event.request_id is not None
            else None
        )
        provider_refund = await self._refund_by_provider_id(event.provider_refund_id)
        if provider_refund is not None and provider_refund.company_id != company_id:
            raise ConflictError("Peach refund ID is already linked to another company")
        handoff_id = (
            requested_refund.handoff_id
            if requested_refund is not None
            else provider_refund.handoff_id
            if provider_refund is not None
            else await self._matching_handoff_id(company_id, event.referenced_capture_id)
        )

        resolution_refund_id: Optional[uuid.UUID] = None
        cancel_actor: Optional[uuid.UUID] = None
        should_cancel = False
        async with unit_of_work(self.db):
            await self._lock_provider_event(event_key, event.provider_refund_id)
            handoff = (
                await self._handoff(handoff_id, company_id, for_update=True)
                if handoff_id is not None
                else None
            )
            existing_event = await self._event_by_identity(
                event_key, event.webhook_id, event.canonical_sha256
            )
            if existing_event is not None:
                if existing_event.company_id != company_id:
                    raise ConflictError(
                        "Peach refund event ID is already linked to another company"
                    )
                return await self._event_response(existing_event, duplicate=True)
            provider_refund = await self._refund_by_provider_id(
                event.provider_refund_id, for_update=True
            )
            if provider_refund is not None and provider_refund.company_id != company_id:
                raise ConflictError("Peach refund ID is already linked to another company")
            order = (
                await self._sales_order(handoff.sales_order_id, for_update=True)
                if handoff is not None
                else None
            )
            credit_note = (
                await self._refund_credit_note_for_order(handoff, order, for_update=True)
                if handoff is not None and order is not None
                else None
            )
            refund = None
            mismatch_code: Optional[str] = None
            binding_error: Optional[str] = None
            if requested_refund is not None:
                refund = await self._refund(event.request_id, company_id, for_update=True)
                if refund.handoff_id != handoff_id:
                    binding_error = "binding_refund_handoff_mismatch"
            if provider_refund is not None:
                if provider_refund is not None:
                    if refund is not None and provider_refund.id != refund.id:
                        binding_error = "binding_provider_refund_id_reused"
                        refund = None
                    else:
                        refund = provider_refund
            elif refund is None and handoff is not None:
                candidates = list(
                    (
                        await self.db.scalars(
                            select(OpsCommerceRefund)
                            .where(
                                OpsCommerceRefund.handoff_id == handoff.id,
                                OpsCommerceRefund.status.in_(OPEN_REFUND_STATES),
                                OpsCommerceRefund.provider_refund_id.is_(None),
                            )
                            .order_by(OpsCommerceRefund.created_at, OpsCommerceRefund.id)
                            .with_for_update()
                        )
                    ).all()
                )
                if candidates:
                    mismatch_code = "provider_event_not_correlated_to_local_intent"
                prior = await self._committed_refunds(handoff.id)
                prior_allocations = self._sum_allocations(prior)
                try:
                    allocation = allocate_refund_cents(
                        handoff.payload, event.amount_minor, prior_allocations
                    )
                except ValidationError:
                    allocation = {}
                    mismatch_code = "provider_refund_exceeds_remaining_capture"
                refund = OpsCommerceRefund(
                    id=uuid.uuid4(),
                    company_id=company_id,
                    handoff_id=handoff.id,
                    sales_order_id=handoff.sales_order_id,
                    requested_by_user_id=None,
                    request_origin="provider",
                    idempotency_key=hashlib.sha256(
                        event.provider_refund_id.encode("utf-8")
                    ).hexdigest(),
                    amount_minor=event.amount_minor,
                    currency_code=event.currency_code,
                    allocation=allocation,
                    selected_lines={},
                    cancel_order=False,
                    status="needs_review" if mismatch_code is not None else "unknown",
                    provider_outcome=event.outcome,
                    provider_refund_id=event.provider_refund_id,
                    provider_amount_minor=event.amount_minor,
                    signature_verified=True,
                    failure_code=mismatch_code,
                )
                self.db.add(refund)
                await self.db.flush()
            elif refund is None and handoff is None:
                mismatch_code = "provider_capture_not_uniquely_matched"
                binding_error = "binding_capture_not_uniquely_matched"

            if refund is not None:
                resolution_refund_id = refund.id
                if refund.status == "needs_review" and refund.failure_code:
                    mismatch_code = mismatch_code or refund.failure_code
                if refund.handoff_id != handoff_id:
                    binding_error = "binding_refund_handoff_mismatch"
                elif handoff is None or order is None:
                    binding_error = "binding_capture_not_uniquely_matched"
                elif handoff.gateway_reference != event.referenced_capture_id:
                    binding_error = "binding_capture_mismatch"
                elif refund.currency_code != event.currency_code:
                    binding_error = "binding_currency_mismatch"
                elif (
                    refund.provider_refund_id is not None
                    and refund.provider_refund_id != event.provider_refund_id
                ):
                    binding_error = "binding_provider_refund_id_mismatch"
                elif (
                    refund.provider_amount_minor is not None
                    and refund.provider_amount_minor != event.amount_minor
                ):
                    binding_error = "binding_provider_amount_mismatch"
                elif refund.provider_outcome == "succeeded" and event.outcome == "failed":
                    binding_error = "binding_provider_outcome_conflict"

                if binding_error is not None:
                    pass
                else:
                    if refund.amount_minor != event.amount_minor:
                        mismatch_code = mismatch_code or "provider_event_amount_differs_from_intent"
                    refund.provider_result_code = event.result_code
                    refund.signature_verified = True
                    refund.provider_amount_minor = event.amount_minor
                    refund.provider_outcome = self._advance_provider_outcome(
                        refund.provider_outcome, event.outcome
                    )
                    if refund.provider_refund_id is None:
                        refund.provider_refund_id = event.provider_refund_id

                if binding_error is None and refund.provider_outcome == "succeeded":
                    refund.status = "needs_review" if mismatch_code else "succeeded"
                    refund.failure_code = mismatch_code
                    if refund.financial_journal_id is None:
                        ledger_error: Optional[str] = None
                        if order is None or handoff is None:
                            ledger_error = "provider_capture_not_uniquely_matched"
                        elif order.invoice_id is not None and credit_note is None:
                            ledger_error = "invoice_requires_accepted_return_reconciliation"
                        elif order.invoice_id is None and order.amount_paid < self._money(
                            event.amount_minor
                        ):
                            ledger_error = "deposit_balance_below_verified_refund"
                        elif await self._exceeds_capture_after_event(handoff):
                            ledger_error = "verified_refund_exceeds_capture"
                        elif (
                            credit_note is not None
                            and await self._exceeds_credit_note_after_event(handoff, credit_note)
                        ):
                            ledger_error = "verified_refund_exceeds_return_credit"
                        else:
                            try:
                                await assert_date_postable(self.db, datetime.date.today())
                            except ConflictError:
                                ledger_error = "refund_date_requires_reconciliation"
                        if ledger_error is not None:
                            refund.status = "needs_review"
                            refund.failure_code = mismatch_code or ledger_error
                        else:
                            amount = self._money(event.amount_minor)
                            debit_code = CODE_AR if order.invoice_id is not None else CODE_DEPOSITS
                            journal = await self.posting.post(
                                JournalDocumentType.PAYMENT,
                                refund.id,
                                f"Verified Storefront refund {event.provider_refund_id}",
                                [
                                    (debit_code, amount, Decimal(0)),
                                    (CODE_STOREFRONT_CLEARING, Decimal(0), amount),
                                ],
                                source="storefront_refund",
                            )
                            refund.financial_journal_id = journal.id
                            refund.completed_at = datetime.datetime.utcnow()
                    if refund.status == "succeeded" and refund.financial_journal_id is not None:
                        should_cancel = bool(refund.cancel_order)
                        cancel_actor = refund.requested_by_user_id
                elif binding_error is None and refund.provider_outcome == "failed":
                    refund.status = "needs_review" if mismatch_code else "failed"
                    refund.failure_code = mismatch_code
                elif binding_error is None and refund.provider_outcome == "pending":
                    refund.status = "needs_review" if mismatch_code else "pending"
                    refund.failure_code = mismatch_code
                elif binding_error is None:
                    refund.status = "needs_review"
                    refund.failure_code = mismatch_code
                if (
                    binding_error is None
                    and order is not None
                    and refund.provider_outcome == "succeeded"
                    and not refund.sales_order_balance_adjusted
                ):
                    order.amount_paid = max(
                        Decimal(0),
                        order.amount_paid - self._money(self._effective_amount(refund)),
                    )
                    refund.sales_order_balance_adjusted = True
                if (
                    binding_error is None
                    and refund.provider_outcome in ("succeeded", "failed")
                    and refund.completed_at is None
                ):
                    refund.completed_at = datetime.datetime.utcnow()

            observation = OpsCommerceRefundEvent(
                id=uuid.uuid4(),
                company_id=company_id,
                handoff_id=handoff.id if handoff is not None else None,
                refund_id=resolution_refund_id,
                provider_refund_id=event.provider_refund_id,
                event_key=event_key,
                webhook_id=event.webhook_id,
                referenced_capture_id=event.referenced_capture_id,
                amount_minor=event.amount_minor,
                currency_code=event.currency_code,
                result_code=event.result_code,
                outcome=event.outcome,
                canonical_sha256=event.canonical_sha256,
                resolution_code=binding_error,
                provider_event_at=event.event_timestamp,
                signature_verified=True,
                received_at=datetime.datetime.utcnow(),
                financial_journal_id=(refund.financial_journal_id if refund is not None else None),
            )
            self.db.add(observation)
            await self.db.flush()

        if should_cancel and handoff_id is not None and resolution_refund_id is not None:
            await self._finish_cancel_after_verified_refund(
                handoff_id,
                resolution_refund_id,
                cancel_actor,
                company_id,
            )
        observation = await self._find_event(event_key, event.webhook_id)
        assert observation is not None
        return await self._event_response(observation, duplicate=False)

    async def _finish_cancel_after_verified_refund(
        self,
        handoff_id: uuid.UUID,
        refund_id: uuid.UUID,
        staff_user_id: Optional[uuid.UUID],
        company_id: uuid.UUID,
    ) -> None:
        try:
            async with unit_of_work(self.db):
                handoff = await self._handoff(handoff_id, company_id, for_update=True)
                refund = await self._refund(refund_id, company_id, for_update=True)
                if handoff.cancelled_at is not None or not refund.cancel_order:
                    return
                if refund.provider_outcome != "succeeded" or refund.status != "succeeded":
                    return
                order = await self._sales_order(refund.sales_order_id, for_update=True)
                if staff_user_id is None:
                    raise ConflictError("Storefront cancellation has no authorized staff actor")
                await SalesOrdersService(self.db).complete_storefront_cancel_after_refund(
                    order, staff_user_id
                )
                handoff.cancelled_at = datetime.datetime.utcnow()
                await StorefrontFulfillmentService(self.db).mark_cancelled(handoff)
                refund.failure_code = None
        except Exception:
            async with unit_of_work(self.db):
                refund = await self._refund(refund_id, company_id, for_update=True)
                refund.status = "needs_review"
                refund.failure_code = "physical_release_requires_staff_review"

    async def _authorize_machine(
        self,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> uuid.UUID:
        return await OpsCommerceService(self.db)._authorize(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )

    async def _committed_refunds(self, handoff_id: uuid.UUID) -> list[OpsCommerceRefund]:
        return list(
            (
                await self.db.scalars(
                    select(OpsCommerceRefund)
                    .where(
                        OpsCommerceRefund.handoff_id == handoff_id,
                        OpsCommerceRefund.status.in_(COMMITTED_REFUND_STATES),
                    )
                    .order_by(OpsCommerceRefund.created_at, OpsCommerceRefund.id)
                )
            ).all()
        )

    async def _exceeds_capture_after_event(self, handoff: OpsCommerceOrder) -> bool:
        committed = await self._committed_refunds(handoff.id)
        total = sum(self._refund_exposure(row) for row in committed)
        return total > handoff.captured_amount_minor

    async def _exceeds_credit_note_after_event(
        self, handoff: OpsCommerceOrder, credit_note: CreditNote
    ) -> bool:
        committed = await self._committed_refunds(handoff.id)
        total = sum(self._refund_exposure(row) for row in committed)
        return total > self._money_to_minor(credit_note.total_inc_vat)

    async def _refund_credit_note_for_order(
        self,
        handoff: OpsCommerceOrder,
        order: SalesOrder,
        *,
        for_update: bool = False,
    ) -> Optional[CreditNote]:
        if order.invoice_id is None:
            return None
        invoice = await TaxInvoiceCRUD(self.db).get_by_id(order.invoice_id, for_update=for_update)
        if invoice is None:
            raise NotFoundError("Storefront invoice not found")
        credit_note = await self.db.scalar(
            select(CreditNote).where(CreditNote.invoice_id == invoice.id)
        )
        if credit_note is None:
            return None
        completed_return = await self.db.scalar(
            select(StockReturn.id).where(
                StockReturn.invoice_id == invoice.id,
                StockReturn.credit_note_id == credit_note.id,
                StockReturn.status == StockReturnStatus.COMPLETED,
            )
        )
        return credit_note if completed_return is not None else None

    async def _matching_handoff_id(
        self, company_id: uuid.UUID, capture_id: str
    ) -> Optional[uuid.UUID]:
        matches = list(
            (
                await self.db.scalars(
                    select(OpsCommerceOrder.id).where(
                        OpsCommerceOrder.company_id == company_id,
                        OpsCommerceOrder.channel == "storefront",
                        OpsCommerceOrder.gateway_reference == capture_id,
                    )
                )
            ).all()
        )
        return matches[0] if len(matches) == 1 else None

    async def _find_event(
        self, event_key: str, webhook_id: Optional[str]
    ) -> Optional[OpsCommerceRefundEvent]:
        identity = OpsCommerceRefundEvent.event_key == event_key
        if webhook_id is not None:
            identity = or_(identity, OpsCommerceRefundEvent.webhook_id == webhook_id)
        return await self.db.scalar(select(OpsCommerceRefundEvent).where(identity))

    async def _lock_provider_event(self, event_key: str, provider_refund_id: str) -> None:
        keys = {
            int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big", signed=True)
            for value in (f"event:{event_key}", f"provider:{provider_refund_id}")
        }
        for key in sorted(keys):
            await self.db.execute(select(func.pg_advisory_xact_lock(key)))

    async def _event_response(
        self, event: OpsCommerceRefundEvent, *, duplicate: bool
    ) -> StorefrontRefundProviderEventResponse:
        refund = (
            await self.db.get(OpsCommerceRefund, event.refund_id)
            if event.refund_id is not None
            else None
        )
        handoff = (
            await self.db.get(OpsCommerceOrder, event.handoff_id)
            if event.handoff_id is not None
            else None
        )
        binding_conflict = event.resolution_code is not None
        status = (
            "needs_review"
            if binding_conflict
            else self._event_resolution_status(refund.status if refund is not None else None)
        )
        provider_outcome = (
            refund.provider_outcome
            if refund is not None and refund.provider_outcome is not None
            else event.outcome
        )
        return StorefrontRefundProviderEventResponse(
            status=status,
            provider_outcome=provider_outcome,
            resolution_code=event.resolution_code,
            request_id=refund.id if refund is not None and not binding_conflict else None,
            external_order_id=(
                handoff.external_order_id if handoff is not None and not binding_conflict else None
            ),
            handoff_id=handoff.id if handoff is not None and not binding_conflict else None,
            amount_minor=event.amount_minor,
            currency_code=event.currency_code,
            provider_refund_id=event.provider_refund_id,
            duplicate=duplicate,
        )

    @staticmethod
    def _event_resolution_status(status: Optional[str]) -> str:
        if status in ("succeeded", "pending", "failed"):
            return status
        return "needs_review"

    async def _refund_by_provider_id(
        self, provider_refund_id: str, *, for_update: bool = False
    ) -> Optional[OpsCommerceRefund]:
        stmt = select(OpsCommerceRefund).where(
            OpsCommerceRefund.provider_refund_id == provider_refund_id
        )
        if for_update:
            stmt = stmt.execution_options(populate_existing=True).with_for_update()
        return await self.db.scalar(stmt)

    async def _refund(
        self, refund_id: uuid.UUID, company_id: uuid.UUID, *, for_update: bool = False
    ) -> OpsCommerceRefund:
        stmt = select(OpsCommerceRefund).where(
            OpsCommerceRefund.id == refund_id,
            OpsCommerceRefund.company_id == company_id,
        )
        if for_update:
            stmt = stmt.execution_options(populate_existing=True).with_for_update()
        row = await self.db.scalar(stmt)
        if row is None:
            raise NotFoundError("Storefront refund was not found")
        return row

    async def _handoff(
        self, handoff_id: uuid.UUID, company_id: uuid.UUID, *, for_update: bool = False
    ) -> OpsCommerceOrder:
        stmt = select(OpsCommerceOrder).where(
            OpsCommerceOrder.id == handoff_id,
            OpsCommerceOrder.company_id == company_id,
            OpsCommerceOrder.channel == "storefront",
        )
        if for_update:
            stmt = stmt.execution_options(populate_existing=True).with_for_update()
        row = await self.db.scalar(stmt)
        if row is None:
            raise NotFoundError("Storefront handoff not found")
        return row

    async def _sales_order(
        self, sales_order_id: uuid.UUID, *, for_update: bool = False
    ) -> SalesOrder:
        stmt = (
            select(SalesOrder)
            .options(
                selectinload(SalesOrder.lines).selectinload(SalesOrderLine.sku),
                selectinload(SalesOrder.payments),
            )
            .where(SalesOrder.id == sales_order_id)
        )
        if for_update:
            stmt = stmt.execution_options(populate_existing=True).with_for_update()
        row = await self.db.scalar(stmt)
        if row is None:
            raise NotFoundError("Sales order not found")
        return row

    @staticmethod
    def _assert_refund_eligible(handoff: OpsCommerceOrder, order: SalesOrder) -> None:
        if handoff.cancelled_at is not None or order.status == SalesOrderStatus.CANCELLED:
            raise ConflictError("Storefront order is already cancelled")
        if handoff.status != "imported":
            raise ConflictError(
                "Storefront order must finish import before a refund can be requested"
            )
        if order.invoice_id is None and order.status not in (
            SalesOrderStatus.OPEN,
            SalesOrderStatus.AWAITING_STOCK,
        ):
            raise ConflictError("Storefront sales order is not eligible for a refund")
        if order.invoice_id is None and handoff.fulfillment_status != "confirmed":
            raise ConflictError("Storefront order is no longer eligible for pre-fulfilment refund")

    async def _require_company_staff(self, staff_user_id: uuid.UUID, company_id: uuid.UUID) -> None:
        user = await self.db.get(User, staff_user_id)
        if user is None or user.team_id != company_id or user.is_disabled:
            raise NotFoundError("Storefront handoff not found")

    async def _event_by_identity(
        self, event_key: str, webhook_id: Optional[str], canonical_sha256: str
    ) -> Optional[OpsCommerceRefundEvent]:
        existing = await self._find_event(event_key, webhook_id)
        if existing is not None and existing.canonical_sha256 != canonical_sha256:
            raise ConflictError("Peach reused a refund event ID with different transaction data")
        return existing

    @staticmethod
    def _sum_allocations(rows: list[OpsCommerceRefund]) -> dict[str, int]:
        totals: dict[str, int] = {}
        for row in rows:
            if row.provider_outcome == "failed" and row.status == "failed":
                continue
            for line_id, amount in row.allocation.items():
                totals[line_id] = totals.get(line_id, 0) + int(amount)
        return totals

    @staticmethod
    def _sum_selected_lines(rows: list[OpsCommerceRefund]) -> dict[str, int]:
        totals: dict[str, int] = {}
        for row in rows:
            if row.provider_outcome == "failed" and row.status == "failed":
                continue
            for line_id, quantity in row.selected_lines.items():
                totals[line_id] = totals.get(line_id, 0) + int(quantity)
        return totals

    @staticmethod
    def _effective_amount(refund: OpsCommerceRefund) -> int:
        if refund.provider_outcome == "succeeded" and refund.provider_amount_minor is not None:
            return refund.provider_amount_minor
        return refund.amount_minor

    @classmethod
    def _effective_reservation(cls, refund: OpsCommerceRefund) -> int:
        if refund.provider_outcome == "succeeded":
            actual = cls._effective_amount(refund)
            return max(0, refund.amount_minor - actual)
        if refund.status == "failed" and refund.provider_outcome == "failed":
            return 0
        return refund.amount_minor

    @classmethod
    def _refund_exposure(cls, refund: OpsCommerceRefund) -> int:
        if refund.provider_outcome == "failed":
            return 0
        if refund.provider_outcome == "succeeded":
            return max(refund.amount_minor, cls._effective_amount(refund))
        return refund.amount_minor

    @staticmethod
    def _refund_response(refund: OpsCommerceRefund) -> StorefrontRefundResponse:
        return StorefrontRefundResponse(
            id=refund.id,
            handoff_id=refund.handoff_id,
            amount_minor=refund.amount_minor,
            provider_amount_minor=refund.provider_amount_minor,
            currency_code=refund.currency_code,
            allocation=refund.allocation,
            selected_lines=refund.selected_lines,
            cancel_order=refund.cancel_order,
            status=refund.status,
            provider_outcome=refund.provider_outcome,
            provider_refund_id=refund.provider_refund_id,
            provider_result_code=refund.provider_result_code,
            failure_code=refund.failure_code,
            signature_verified=refund.signature_verified,
            financial_journal_id=refund.financial_journal_id,
            created_at=refund.created_at,
            completed_at=refund.completed_at,
        )

    @classmethod
    def _advance_provider_outcome(cls, current: Optional[str], observed: str) -> str:
        if current == "succeeded":
            return "succeeded"
        if current == "failed" and observed != "succeeded":
            return "failed"
        if observed == "succeeded":
            return "succeeded"
        if observed == "failed":
            return "failed"
        if current == "pending" or observed == "pending":
            return "pending"
        return "unknown"

    @staticmethod
    def _money(amount_minor: int) -> Decimal:
        return (Decimal(amount_minor) / Decimal(100)).quantize(CENT)

    @classmethod
    def _money_to_minor(cls, amount: Decimal) -> int:
        return int((amount * 100).quantize(Decimal("1")))
