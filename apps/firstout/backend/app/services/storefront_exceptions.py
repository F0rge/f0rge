from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.storefront_exceptions import StorefrontExceptionCRUD
from app.exceptions import ForbiddenError
from app.models.storefront_commerce_exception import (
    FINANCIAL_KINDS,
    StorefrontCommerceException,
    StorefrontExceptionAlert,
    StorefrontExceptionAudit,
)
from app.models.user import User
from app.permissions import SALES_ORDERS, SALES_REFUNDS
from app.schemas.storefront_exceptions import (
    StorefrontCheckoutSafetyResponse,
    StorefrontExceptionAlertListResponse,
    StorefrontExceptionAlertRequest,
    StorefrontExceptionAlertResponse,
    StorefrontExceptionAuditResponse,
    StorefrontExceptionListResponse,
    StorefrontExceptionRepairRequest,
    StorefrontExceptionResponse,
)
from app.services.permissions import PermissionService
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

HANDOFF_AGED_SECONDS = 5 * 60

SEED_SPECS: tuple[dict[str, object], ...] = (
    {
        "seed_key": "aged_hold",
        "kind": "aged_hold",
        "status": "aged",
        "age_minutes": 18,
        "explanation": "Checkout hold is older than its TTL and still occupies projected stock.",
        "safe_action": "release_expired_hold",
        "last_error": "hold_expired",
        "correlation_id": "storefront:hold:seed-aged",
    },
    {
        "seed_key": "stale_sync",
        "kind": "stale_sync",
        "status": "aged",
        "age_minutes": 12,
        "explanation": "Operational stock projection is older than the five-minute freshness window.",
        "safe_action": "refresh_projection",
        "last_error": "projection_stale",
        "correlation_id": "storefront:sync:seed-stale",
        "blocks_checkout": True,
    },
    {
        "seed_key": "missing_operational_paid_order",
        "kind": "missing_operational_paid_order",
        "status": "aged",
        "age_minutes": 9,
        "explanation": "A captured payment has no imported operational sales order.",
        "safe_action": "retry_handoff",
        "last_error": "ops_unavailable",
        "correlation_id": "storefront:order:seed-missing-handoff",
    },
    {
        "seed_key": "unknown_payment",
        "kind": "unknown_payment",
        "status": "open",
        "age_minutes": 7,
        "explanation": "A hosted payment callback is unverified. Do not mark it successful.",
        "safe_action": "verify_with_provider",
        "last_error": "initiation_unknown",
        "correlation_id": "storefront:pay:seed-unknown",
        "amount_minor": 115000,
        "payment_reference": "seed-pay-unknown",
        "customer_email": "payer@example.test",
        "provider_verified": False,
    },
    {
        "seed_key": "refund_mismatch",
        "kind": "refund_mismatch",
        "status": "open",
        "age_minutes": 6,
        "explanation": "Local refund projection disagrees with a verified provider observation.",
        "safe_action": "reproject_verified_refund",
        "last_error": "refund_amount_mismatch",
        "correlation_id": "storefront:refund:seed-mismatch",
        "amount_minor": 57500,
        "payment_reference": "seed-refund-mismatch",
        "customer_email": "refund@example.test",
        "provider_verified": True,
    },
    {
        "seed_key": "fulfilment_drift",
        "kind": "fulfilment_drift",
        "status": "open",
        "age_minutes": 8,
        "explanation": "Storefront fulfilment status is behind the operational event feed.",
        "safe_action": "resync_fulfillment",
        "last_error": "revision_gap",
        "correlation_id": "storefront:fulfill:seed-drift",
    },
    {
        "seed_key": "capacity_conflict",
        "kind": "capacity_conflict",
        "status": "terminal",
        "age_minutes": 20,
        "explanation": "Paid made-to-order capacity cannot be restored from a later catalogue snapshot.",
        "safe_action": "acknowledge_capacity",
        "last_error": "capacity_exhausted",
        "correlation_id": "storefront:capacity:seed-conflict",
    },
)


def redact_alert_context(
    *,
    kind: str,
    status: str,
    age_seconds: int,
    correlation_id: str,
    last_error: Optional[str],
    blocks_checkout: bool,
) -> dict[str, object]:
    return {
        "kind": kind,
        "status": status,
        "age_seconds": age_seconds,
        "correlation_id": correlation_id,
        "last_error": last_error,
        "blocks_checkout": blocks_checkout,
        "handoff_aged_threshold_seconds": HANDOFF_AGED_SECONDS,
    }


def queue_class_for(status: str, age_seconds: int) -> str:
    if status == "terminal":
        return "terminal"
    if status == "aged" or age_seconds >= HANDOFF_AGED_SECONDS:
        return "aged"
    return "retrying"


class StorefrontExceptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = StorefrontExceptionCRUD(db)
        self.permissions = PermissionService(db)

    async def list_exceptions(self, staff_user_id: uuid.UUID) -> StorefrontExceptionListResponse:
        company_id, can_orders, can_refunds = await self._staff_access(staff_user_id)
        rows = await self.crud.list_for_company(company_id)
        blocking = await self.crud.blocking_open(company_id)
        return StorefrontExceptionListResponse(
            items=[self._item(row, can_orders=can_orders, can_refunds=can_refunds) for row in rows],
            checkout_allowed=not blocking,
        )

    async def get_exception(
        self, exception_id: uuid.UUID, staff_user_id: uuid.UUID
    ) -> StorefrontExceptionResponse:
        company_id, can_orders, can_refunds = await self._staff_access(staff_user_id)
        row = await self._owned(exception_id, company_id)
        audits = await self.crud.audits_for(row.id)
        item = self._item(row, can_orders=can_orders, can_refunds=can_refunds)
        item.audits = [StorefrontExceptionAuditResponse.model_validate(audit) for audit in audits]
        return item

    async def seed_fixtures(self, staff_user_id: uuid.UUID) -> StorefrontExceptionListResponse:
        if not settings.storefront_exception_fixtures:
            raise ForbiddenError("Exception fixtures are disabled")
        company_id, can_orders, can_refunds = await self._staff_access(staff_user_id)
        if not can_orders:
            raise ForbiddenError("Seeding commerce exceptions requires sales.orders")
        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            for spec in SEED_SPECS:
                seed_key = str(spec["seed_key"])
                existing = await self.crud.get_by_seed_key(company_id, seed_key)
                if existing is not None:
                    continue
                age_minutes = int(spec["age_minutes"])
                amount = spec.get("amount_minor")
                await self.crud.add(
                    StorefrontCommerceException(
                        company_id=company_id,
                        kind=str(spec["kind"]),
                        status=str(spec["status"]),
                        seed_key=seed_key,
                        correlation_id=str(spec["correlation_id"]),
                        explanation=str(spec["explanation"]),
                        safe_action=str(spec["safe_action"]),
                        last_error=str(spec["last_error"]) if spec.get("last_error") else None,
                        amount_minor=amount if isinstance(amount, int) else None,
                        payment_reference=(
                            str(spec["payment_reference"])
                            if spec.get("payment_reference")
                            else None
                        ),
                        customer_email=(
                            str(spec["customer_email"]) if spec.get("customer_email") else None
                        ),
                        provider_verified=bool(spec.get("provider_verified", False)),
                        blocks_checkout=bool(spec.get("blocks_checkout", False)),
                        detected_at=now - datetime.timedelta(minutes=age_minutes),
                    )
                )
        return await self.list_exceptions(staff_user_id)

    async def repair(
        self,
        exception_id: uuid.UUID,
        body: StorefrontExceptionRepairRequest,
        staff_user_id: uuid.UUID,
    ) -> StorefrontExceptionResponse:
        company_id, can_orders, can_refunds = await self._staff_access(staff_user_id)
        provider_required = False
        async with unit_of_work(self.db):
            row = await self.crud.get_by_id(exception_id, for_update=True)
            if row is None or row.company_id != company_id:
                raise NotFoundError("Commerce exception not found")
            financial = row.kind in FINANCIAL_KINDS
            if financial and not can_refunds:
                raise ForbiddenError("Restricted financial repair requires sales.refunds")
            if not financial and not can_orders:
                raise ForbiddenError("Operational repair requires sales.orders")
            existing = await self.crud.audit_by_key(row.id, body.idempotency_key)
            if existing is not None:
                if existing.outcome == "needs_provider":
                    provider_required = True
                else:
                    return await self.get_exception(row.id, staff_user_id)
            elif financial and not row.provider_verified:
                await self.crud.add_audit(
                    StorefrontExceptionAudit(
                        exception_id=row.id,
                        actor_user_id=staff_user_id,
                        idempotency_key=body.idempotency_key,
                        reason=body.reason.strip(),
                        outcome="needs_provider",
                        detail="Payment success cannot be recorded without provider verification",
                    )
                )
                provider_required = True
            elif row.status == "resolved":
                await self.crud.add_audit(
                    StorefrontExceptionAudit(
                        exception_id=row.id,
                        actor_user_id=staff_user_id,
                        idempotency_key=body.idempotency_key,
                        reason=body.reason.strip(),
                        outcome="already_resolved",
                        detail="Repair already converged",
                    )
                )
            else:
                row.status = "resolved"
                row.resolved_at = datetime.datetime.utcnow()
                row.blocks_checkout = False
                if not row.effect_applied:
                    row.effect_applied = True
                    row.repair_count += 1
                await self.crud.add_audit(
                    StorefrontExceptionAudit(
                        exception_id=row.id,
                        actor_user_id=staff_user_id,
                        idempotency_key=body.idempotency_key,
                        reason=body.reason.strip(),
                        outcome="repaired",
                        detail=row.safe_action,
                    )
                )
        if provider_required:
            raise ValidationError(
                "Payment success cannot be recorded without provider verification"
            )
        return await self.get_exception(exception_id, staff_user_id)

    async def deliver_test_alert(
        self, body: StorefrontExceptionAlertRequest, staff_user_id: uuid.UUID
    ) -> StorefrontExceptionAlertResponse:
        company_id, can_orders, can_refunds = await self._staff_access(staff_user_id)
        if body.exception_id is None:
            rows = await self.crud.list_for_company(company_id)
            row = next(
                (item for item in rows if item.kind == "missing_operational_paid_order"), None
            )
            if row is None:
                raise NotFoundError("No handoff exception is available for an alert")
        else:
            row = await self._owned(body.exception_id, company_id)
        if row.kind in FINANCIAL_KINDS and not can_refunds:
            raise ForbiddenError("Restricted financial alerts require sales.refunds")
        if row.kind not in FINANCIAL_KINDS and not can_orders and not can_refunds:
            raise ForbiddenError("Exception alerts are not available to this user")
        age_seconds = self._age_seconds(row)
        context = redact_alert_context(
            kind=row.kind,
            status=row.status,
            age_seconds=age_seconds,
            correlation_id=row.correlation_id,
            last_error=row.last_error,
            blocks_checkout=row.blocks_checkout,
        )
        async with unit_of_work(self.db):
            alert = await self.crud.add_alert(
                StorefrontExceptionAlert(
                    company_id=company_id,
                    exception_id=row.id,
                    kind=row.kind,
                    queue_class=queue_class_for(row.status, age_seconds),
                    context=context,
                )
            )
        return StorefrontExceptionAlertResponse.model_validate(alert)

    async def list_test_alerts(
        self, staff_user_id: uuid.UUID
    ) -> StorefrontExceptionAlertListResponse:
        company_id, _, _ = await self._staff_access(staff_user_id)
        rows = await self.crud.list_alerts(company_id)
        return StorefrontExceptionAlertListResponse(
            items=[StorefrontExceptionAlertResponse.model_validate(row) for row in rows]
        )

    async def checkout_safety(self, company_id: uuid.UUID) -> StorefrontCheckoutSafetyResponse:
        blocking = await self.crud.blocking_open(company_id)
        if not blocking:
            return StorefrontCheckoutSafetyResponse(checkout_allowed=True, reason=None)
        kinds = sorted({row.kind for row in blocking})
        reason = "Operational outage or stale projection blocks new checkout"
        if "stale_sync" in kinds:
            reason = "Stock projection is stale; new checkout is blocked"
        return StorefrontCheckoutSafetyResponse(checkout_allowed=False, reason=reason)

    async def _staff_access(self, staff_user_id: uuid.UUID) -> tuple[uuid.UUID, bool, bool]:
        staff = await self.db.get(User, staff_user_id)
        if staff is None or staff.is_disabled or staff.role == "system":
            raise ForbiddenError("Storefront exceptions are not available to this user")
        can_orders = await self.permissions.has_permission(staff_user_id, SALES_ORDERS)
        can_refunds = await self.permissions.has_permission(staff_user_id, SALES_REFUNDS)
        if not can_orders and not can_refunds:
            raise ForbiddenError("Storefront exceptions are not available to this user")
        return staff.team_id, can_orders, can_refunds

    async def _owned(
        self, exception_id: uuid.UUID, company_id: uuid.UUID
    ) -> StorefrontCommerceException:
        row = await self.crud.get_by_id(exception_id)
        if row is None or row.company_id != company_id:
            raise NotFoundError("Commerce exception not found")
        return row

    def _item(
        self,
        row: StorefrontCommerceException,
        *,
        can_orders: bool,
        can_refunds: bool,
    ) -> StorefrontExceptionResponse:
        financial = row.kind in FINANCIAL_KINDS
        show_finance = can_refunds
        can_repair = can_refunds if financial else can_orders
        return StorefrontExceptionResponse(
            id=row.id,
            kind=row.kind,
            status=row.status,
            age_seconds=self._age_seconds(row),
            correlation_id=row.correlation_id,
            explanation=row.explanation,
            safe_action=row.safe_action,
            last_error=row.last_error,
            financial=financial,
            amount_minor=row.amount_minor if show_finance else None,
            payment_reference=row.payment_reference if show_finance else None,
            provider_verified=row.provider_verified if show_finance else False,
            blocks_checkout=row.blocks_checkout,
            can_repair=can_repair and row.status != "resolved",
            detected_at=row.detected_at,
            resolved_at=row.resolved_at,
            repair_count=row.repair_count,
        )

    @staticmethod
    def _age_seconds(row: StorefrontCommerceException) -> int:
        delta = datetime.datetime.utcnow() - row.detected_at
        return max(0, int(delta.total_seconds()))
