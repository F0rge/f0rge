from __future__ import annotations

import datetime
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.storefront_exceptions import StorefrontExceptionCRUD
from app.exceptions import ForbiddenError
from app.models.storefront_commerce_exception import (
    StorefrontCommerceException,
    StorefrontExceptionAlert,
    StorefrontExceptionAudit,
)
from app.models.user import User
from app.permissions import SALES_ORDERS, SALES_REFUNDS
from app.schemas.storefront_exceptions import StorefrontExceptionAlertResponse
from app.schemas.storefront_recovery import (
    ProposedBackupPolicyResponse,
    StorefrontBackupCheckRequest,
    StorefrontBackupCheckResponse,
    StorefrontRecoveryAlertRequest,
    StorefrontRecoveryOpenRequest,
    StorefrontRecoveryReconcileRequest,
    StorefrontRecoveryReplayRequest,
    StorefrontRecoveryResponse,
)
from app.services.permissions import PermissionService
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

EFFECTS = ("payment", "refund", "order", "operational_posting", "email")
TRUTHS = ("provider", "order", "stock", "capacity")
DURABLE_DATASETS = (
    "commerce_postgres",
    "payment_attempts",
    "refund_ledger",
    "order_handoff_outbox",
    "notification_outbox",
    "capacity_reservations",
    "ops_exception_queue",
)
PROPOSED_BACKUP_POLICY = {
    "status": "proposal",
    "agreed_sla": False,
    "daily_copies": 14,
    "recovery_point_hours": 24,
    "restoration_hours_after_operator_start": 4,
}
GATE_TRUTHS = (
    "Restored checkout stays gated until provider, order, stock, and capacity are reconciled"
)
FIRSTOUT_DEPENDENCY = (
    "Firstout is a required dependency. Checkout stays gated until operations are reachable."
)
RECOVERY_POINT = datetime.timedelta(hours=PROPOSED_BACKUP_POLICY["recovery_point_hours"])
RESTORATION_LIMIT = datetime.timedelta(
    hours=PROPOSED_BACKUP_POLICY["restoration_hours_after_operator_start"]
)
_RESTORE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,39}$")
_BACKUP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FINANCIAL_EFFECTS = frozenset({"payment", "refund"})
_QUEUE_CLASS = {
    "stale_stock": "aged",
    "aged_paid_handoff": "aged",
    "backup_stale": "aged",
    "webhook_failure": "retrying",
    "job_failure": "retrying",
    "email_failure": "retrying",
    "spending": "terminal",
    "backup_missing": "terminal",
    "backup_corrupt": "terminal",
}
_SLOT_KIND = {
    "payment": "unknown_payment",
    "refund": "refund_mismatch",
    "order": "missing_operational_paid_order",
    "stock": "stale_sync",
    "capacity": "capacity_conflict",
}
_SLOT_ACTION = {
    "payment": "verify_with_provider",
    "refund": "reproject_verified_refund",
    "order": "retry_handoff",
    "stock": "refresh_projection",
    "capacity": "acknowledge_capacity",
}
_SLOT_EXPLANATION = {
    "payment": "Restored snapshot is missing a later verified payment.",
    "refund": "Restored snapshot is missing a later verified refund.",
    "order": "Restored snapshot is missing the operational order for a later payment.",
    "stock": "Restored stock must be reconciled before checkout reopens.",
    "capacity": "Restored made-to-order capacity must be acknowledged before checkout reopens.",
}


@dataclass
class RecoveryState:
    restore_id: str
    later_payment: bool
    later_refund: bool
    truths: dict[str, str]
    effects: dict[str, int]
    seen_keys: dict[str, str]
    ops_reachable: bool = False

    @property
    def checkout(self) -> str:
        ready = all(self.truths[name] == "reconciled" for name in TRUTHS)
        if ready and self.ops_reachable:
            return "open"
        return "gated"


@dataclass(frozen=True)
class RowView:
    seed_key: str
    status: str


@dataclass(frozen=True)
class AuditView:
    idempotency_key: str
    outcome: str
    detail: Optional[str]


@dataclass(frozen=True)
class RouteAlert:
    route: str
    queue_class: str
    message: str
    context: dict[str, object]


@dataclass(frozen=True)
class BackupAssessment:
    ok: bool
    code: str
    message: Optional[str]
    alert: Optional[RouteAlert]


def _effects() -> dict[str, int]:
    return {name: 0 for name in EFFECTS}


def _truths() -> dict[str, str]:
    return {name: "pending" for name in TRUTHS}


def clone_recovery(state: RecoveryState) -> RecoveryState:
    return RecoveryState(
        restore_id=state.restore_id,
        later_payment=state.later_payment,
        later_refund=state.later_refund,
        truths=dict(state.truths),
        effects=dict(state.effects),
        seen_keys=dict(state.seen_keys),
        ops_reachable=state.ops_reachable,
    )


def resume_recovery(state: RecoveryState) -> RecoveryState:
    return clone_recovery(state)


def restore_correlation(restore_id: str) -> str:
    return f"storefront:restore:{restore_id}"


def restore_seed(restore_id: str, slot: str) -> str:
    return f"restore:{restore_id}:{slot}"


def gate_reason(state: RecoveryState) -> Optional[str]:
    if state.checkout == "open":
        return None
    ready = all(state.truths[name] == "reconciled" for name in TRUTHS)
    if ready and not state.ops_reachable:
        return FIRSTOUT_DEPENDENCY
    return GATE_TRUTHS


def open_restore(restore_id: str, *, later_payment: bool, later_refund: bool) -> RecoveryState:
    if not _RESTORE_ID.match(restore_id):
        raise ValueError("restore_id is invalid")
    if not later_payment and not later_refund:
        raise ValueError("A later verified payment or refund is required")
    return RecoveryState(
        restore_id=restore_id,
        later_payment=later_payment,
        later_refund=later_refund,
        truths=_truths(),
        effects=_effects(),
        seen_keys={},
        ops_reachable=False,
    )


def with_ops(state: RecoveryState, ops_reachable: bool) -> RecoveryState:
    nxt = clone_recovery(state)
    nxt.ops_reachable = ops_reachable
    return nxt


def replay_effect(
    state: RecoveryState,
    effect: str,
    idempotency_key: str,
    *,
    provider_verified: bool,
) -> tuple[RecoveryState, str]:
    if effect not in EFFECTS:
        return state, "rejected"
    if effect in _FINANCIAL_EFFECTS and not provider_verified:
        return state, "needs_provider"
    if effect == "payment" and not state.later_payment:
        return state, "rejected"
    if effect == "refund" and not state.later_refund:
        return state, "rejected"
    if idempotency_key in state.seen_keys:
        return state, "duplicate"
    nxt = clone_recovery(state)
    if nxt.effects[effect] >= 1:
        nxt.seen_keys[idempotency_key] = effect
        return nxt, "duplicate"
    nxt.effects[effect] = 1
    nxt.seen_keys[idempotency_key] = effect
    return nxt, "applied"


def reconcile_truth(
    state: RecoveryState, truth: str, *, provider_verified: bool
) -> tuple[RecoveryState, str]:
    if truth not in TRUTHS:
        return state, "rejected"
    if state.truths[truth] == "reconciled":
        return state, "already_reconciled"
    if truth == "provider":
        if not provider_verified:
            return state, "needs_provider"
        if not state.later_payment and not state.later_refund:
            return state, "rejected"
        if state.later_payment and state.effects["payment"] != 1:
            return state, "needs_effect"
        if state.later_refund and state.effects["refund"] != 1:
            return state, "needs_effect"
    elif truth == "order":
        if state.effects["order"] != 1 or state.effects["operational_posting"] != 1:
            return state, "needs_effect"
    nxt = clone_recovery(state)
    nxt.truths[truth] = "reconciled"
    return nxt, "reconciled"


def public_backup_id(value: object) -> str:
    if isinstance(value, str) and _BACKUP_ID.match(value):
        return value
    return "redacted"


def dataset_label(value: object) -> str:
    if isinstance(value, str) and value in DURABLE_DATASETS:
        return value
    return "required durable state"


def route_alert(route: str, raw: Optional[dict[str, object]] = None) -> RouteAlert:
    payload = raw or {}
    backup_id = public_backup_id(payload.get("backup_id"))
    dataset = dataset_label(payload.get("dataset"))
    show_id = backup_id != "redacted"
    identity = backup_id if show_id else "redacted"
    if route == "stale_stock":
        message = (
            "Stock projection is stale. Checkout stays gated until stock truth is "
            "reconciled. Refresh the projection and do not decrement stock again."
        )
    elif route == "aged_paid_handoff":
        message = (
            "Paid handoff is older than five minutes. Replay the existing handoff "
            "key and do not create a second order."
        )
    elif route == "webhook_failure":
        message = (
            "A payment webhook failed. Replay the stored callback only after "
            "provider verification and do not capture a second payment."
        )
    elif route == "job_failure":
        message = (
            "A durable job failed. Restart resumes the same idempotency key and "
            "does not post a second operational effect."
        )
    elif route == "email_failure":
        message = (
            "An order email failed. Replay uses the notification idempotency key "
            "and does not send a second message."
        )
    elif route == "spending":
        message = (
            "A spending signal needs operator review. Checkout stays gated. "
            "This alert includes no customer or payment data."
        )
    elif route == "backup_missing":
        message = (
            f"Backup {identity} is missing durable dataset {dataset}. "
            "Checkout stays gated. Take a new protected copy and do not restore this one."
        )
    elif route == "backup_corrupt":
        message = f"Backup {identity} is corrupt. Checkout stays gated. Do not restore this copy."
    else:
        message = (
            f"Backup {identity} is older than the proposed 24-hour recovery point. "
            "That point is a proposal, not an agreed SLA. Checkout stays gated."
        )
    context: dict[str, object] = {
        "route": route,
        "message": message,
        "action": "keep_checkout_gated",
        "agreed_sla": False,
        "live_restore": False,
    }
    if show_id and route in {"backup_missing", "backup_corrupt", "backup_stale"}:
        context["backup_id"] = backup_id
    if dataset != "required durable state" and route == "backup_missing":
        context["dataset"] = dataset
    return RouteAlert(
        route=route,
        queue_class=_QUEUE_CLASS.get(route, "terminal"),
        message=message,
        context=context,
    )


def _as_utc_naive(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def assess_backup(
    manifest: Optional[dict[str, object]], now: datetime.datetime
) -> BackupAssessment:
    if manifest is None:
        alert = route_alert("backup_missing", {})
        return BackupAssessment(False, "missing", alert.message, alert)
    backup_id = manifest.get("backup_id")
    if manifest.get("credentials_included") is True:
        alert = route_alert("backup_corrupt", {"backup_id": backup_id})
        return BackupAssessment(False, "corrupt", alert.message, alert)
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        alert = route_alert("backup_corrupt", {"backup_id": backup_id})
        return BackupAssessment(False, "corrupt", alert.message, alert)
    names: list[str] = []
    for item in datasets:
        if not isinstance(item, dict):
            alert = route_alert("backup_corrupt", {"backup_id": backup_id})
            return BackupAssessment(False, "corrupt", alert.message, alert)
        name = item.get("name")
        names.append(name if isinstance(name, str) else "")
    if len(set(names)) != len(names):
        alert = route_alert("backup_corrupt", {"backup_id": backup_id})
        return BackupAssessment(False, "corrupt", alert.message, alert)
    for required in DURABLE_DATASETS:
        if required not in names:
            alert = route_alert("backup_missing", {"backup_id": backup_id, "dataset": required})
            return BackupAssessment(False, "missing", alert.message, alert)
    for item in datasets:
        size = item.get("byte_size")
        digest = item.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            alert = route_alert("backup_corrupt", {"backup_id": backup_id})
            return BackupAssessment(False, "corrupt", alert.message, alert)
        if not isinstance(digest, str) or _SHA256.match(digest) is None:
            alert = route_alert("backup_corrupt", {"backup_id": backup_id})
            return BackupAssessment(False, "corrupt", alert.message, alert)
    captured = manifest.get("captured_at")
    if not isinstance(captured, datetime.datetime):
        alert = route_alert("backup_corrupt", {"backup_id": backup_id})
        return BackupAssessment(False, "corrupt", alert.message, alert)
    captured_at = _as_utc_naive(captured)
    current = _as_utc_naive(now)
    if captured_at - current > datetime.timedelta(minutes=5):
        alert = route_alert("backup_corrupt", {"backup_id": backup_id})
        return BackupAssessment(False, "corrupt", alert.message, alert)
    if current - captured_at > RECOVERY_POINT:
        alert = route_alert("backup_stale", {"backup_id": backup_id})
        return BackupAssessment(False, "stale", alert.message, alert)
    return BackupAssessment(True, "ok", None, None)


def measure_clocks(
    *,
    captured_at: Optional[datetime.datetime],
    now: datetime.datetime,
    operator_started_at: Optional[datetime.datetime],
    operator_finished_at: Optional[datetime.datetime],
) -> dict[str, object]:
    age_ms: Optional[int] = None
    within_rpo = False
    if captured_at is not None:
        delta = _as_utc_naive(now) - _as_utc_naive(captured_at)
        age_ms = int(delta.total_seconds() * 1000)
        within_rpo = datetime.timedelta(0) <= delta <= RECOVERY_POINT
    elapsed_ms: Optional[int] = None
    within_restoration: Optional[bool] = None
    if operator_started_at is not None and operator_finished_at is not None:
        elapsed = _as_utc_naive(operator_finished_at) - _as_utc_naive(operator_started_at)
        elapsed_ms = int(elapsed.total_seconds() * 1000)
        within_restoration = datetime.timedelta(0) <= elapsed <= RESTORATION_LIMIT
    return {
        "backup_age_ms": age_ms,
        "rehearsal_elapsed_ms": elapsed_ms,
        "within_proposed_recovery_point": within_rpo,
        "within_proposed_restoration": within_restoration,
        "live_restore": False,
        "agreed_sla": False,
    }


def state_from_rows(
    restore_id: str,
    rows: list[RowView],
    audits: list[AuditView],
    *,
    ops_reachable: bool,
) -> RecoveryState:
    later_payment = any(row.seed_key.endswith(":payment") for row in rows)
    later_refund = any(row.seed_key.endswith(":refund") for row in rows)
    by_slot: dict[str, str] = {}
    for row in rows:
        by_slot[row.seed_key.rsplit(":", 1)[-1]] = row.status
    truths = _truths()
    financial = [slot for slot in ("payment", "refund") if slot in by_slot]
    if financial and all(by_slot[slot] == "resolved" for slot in financial):
        truths["provider"] = "reconciled"
    for slot in ("order", "stock", "capacity"):
        if by_slot.get(slot) == "resolved":
            truths[slot] = "reconciled"
    effects = _effects()
    seen: dict[str, str] = {}
    for audit in audits:
        detail = audit.detail or ""
        if detail.startswith("effect:") and audit.outcome == "repaired":
            effect = detail[len("effect:") :]
            if effect in effects:
                effects[effect] += 1
            seen[audit.idempotency_key] = effect
        elif detail.startswith("effect:") and audit.outcome == "already_resolved":
            seen[audit.idempotency_key] = detail[len("effect:") :]
        elif detail.startswith("truth:"):
            seen[audit.idempotency_key] = detail
    return RecoveryState(
        restore_id=restore_id,
        later_payment=later_payment,
        later_refund=later_refund,
        truths=truths,
        effects=effects,
        seen_keys=seen,
        ops_reachable=ops_reachable,
    )


def proposal_model() -> ProposedBackupPolicyResponse:
    return ProposedBackupPolicyResponse(
        status="proposal",
        agreed_sla=False,
        daily_copies=int(PROPOSED_BACKUP_POLICY["daily_copies"]),
        recovery_point_hours=int(PROPOSED_BACKUP_POLICY["recovery_point_hours"]),
        restoration_hours_after_operator_start=int(
            PROPOSED_BACKUP_POLICY["restoration_hours_after_operator_start"]
        ),
    )


def _slot_for_effect(effect: str) -> str:
    if effect == "payment":
        return "payment"
    if effect == "refund":
        return "refund"
    return "order"


class StorefrontRecoveryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = StorefrontExceptionCRUD(db)
        self.permissions = PermissionService(db)

    async def open_restore(
        self, body: StorefrontRecoveryOpenRequest, staff_user_id: uuid.UUID
    ) -> StorefrontRecoveryResponse:
        if not body.later_payment and not body.later_refund:
            raise ValidationError("A later verified payment or refund is required")
        company_id, can_orders, _can_refunds = await self._staff(staff_user_id)
        if not can_orders:
            raise ForbiddenError("Opening a restore requires sales.orders")
        async with unit_of_work(self.db):
            existing = await self.crud.list_by_correlation(
                company_id, restore_correlation(body.restore_id)
            )
            slots = self._slots_for(body, existing)
            for slot in slots:
                seed_key = restore_seed(body.restore_id, slot)
                if await self.crud.get_by_seed_key(company_id, seed_key) is not None:
                    continue
                await self.crud.add(
                    StorefrontCommerceException(
                        company_id=company_id,
                        kind=_SLOT_KIND[slot],
                        status="open",
                        seed_key=seed_key,
                        correlation_id=restore_correlation(body.restore_id),
                        explanation=_SLOT_EXPLANATION[slot],
                        safe_action=_SLOT_ACTION[slot],
                        last_error="restore_gap",
                        provider_verified=False,
                        blocks_checkout=True,
                        effect_applied=False,
                        repair_count=0,
                        detected_at=datetime.datetime.utcnow(),
                    )
                )
        return await self.view(body.restore_id, staff_user_id, ops_reachable=False)

    async def replay(
        self, body: StorefrontRecoveryReplayRequest, staff_user_id: uuid.UUID
    ) -> StorefrontRecoveryResponse:
        company_id, can_orders, can_refunds = await self._staff(staff_user_id)
        self._require_effect(body.effect, can_orders=can_orders, can_refunds=can_refunds)
        async with unit_of_work(self.db):
            slot = _slot_for_effect(body.effect)
            row = await self.crud.get_by_seed_key(
                company_id, restore_seed(body.restore_id, slot), for_update=True
            )
            if row is None:
                raise NotFoundError("Restore recovery was not found")
            state = await self._load(company_id, body.restore_id, ops_reachable=False)
            _nxt, outcome = replay_effect(
                state,
                body.effect,
                body.idempotency_key,
                provider_verified=body.provider_verified,
            )
            self._raise_for_replay(outcome)
            if outcome == "applied" or (
                outcome == "duplicate" and body.idempotency_key not in state.seen_keys
            ):
                detail = f"effect:{body.effect}"
                if outcome == "applied":
                    row.effect_applied = True
                    row.repair_count += 1
                    if body.effect in _FINANCIAL_EFFECTS and body.provider_verified:
                        row.provider_verified = True
                    audit_outcome = "repaired"
                else:
                    audit_outcome = "already_resolved"
                await self.crud.add_audit(
                    StorefrontExceptionAudit(
                        exception_id=row.id,
                        actor_user_id=staff_user_id,
                        idempotency_key=body.idempotency_key,
                        reason=body.reason.strip(),
                        outcome=audit_outcome,
                        detail=detail,
                    )
                )
        return await self.view(body.restore_id, staff_user_id, ops_reachable=False)

    async def reconcile(
        self, body: StorefrontRecoveryReconcileRequest, staff_user_id: uuid.UUID
    ) -> StorefrontRecoveryResponse:
        company_id, can_orders, can_refunds = await self._staff(staff_user_id)
        self._require_truth(body.truth, can_orders=can_orders, can_refunds=can_refunds)
        async with unit_of_work(self.db):
            state = await self._load(company_id, body.restore_id, ops_reachable=False)
            if body.idempotency_key in state.seen_keys and state.truths[body.truth] != "reconciled":
                raise ValidationError("Idempotency key was already used")
            _nxt, outcome = reconcile_truth(
                state, body.truth, provider_verified=body.provider_verified
            )
            self._raise_for_reconcile(outcome)
            if outcome == "reconciled":
                slots = self._truth_slots(state, body.truth)
                primary: Optional[StorefrontCommerceException] = None
                now = datetime.datetime.utcnow()
                for slot in slots:
                    row = await self.crud.get_by_seed_key(
                        company_id, restore_seed(body.restore_id, slot), for_update=True
                    )
                    if row is None:
                        raise NotFoundError("Restore recovery was not found")
                    row.status = "resolved"
                    row.blocks_checkout = False
                    row.resolved_at = now
                    if body.truth == "provider" and body.provider_verified:
                        row.provider_verified = True
                    if primary is None:
                        primary = row
                if primary is None:
                    raise NotFoundError("Restore recovery was not found")
                await self.crud.add_audit(
                    StorefrontExceptionAudit(
                        exception_id=primary.id,
                        actor_user_id=staff_user_id,
                        idempotency_key=body.idempotency_key,
                        reason=body.reason.strip(),
                        outcome="repaired",
                        detail=f"truth:{body.truth}",
                    )
                )
        return await self.view(body.restore_id, staff_user_id, ops_reachable=False)

    async def view(
        self, restore_id: str, staff_user_id: uuid.UUID, *, ops_reachable: bool
    ) -> StorefrontRecoveryResponse:
        company_id, _can_orders, _can_refunds = await self._staff(staff_user_id)
        state = await self._load(company_id, restore_id, ops_reachable=ops_reachable)
        return self._response(state)

    async def check_backup(
        self, body: StorefrontBackupCheckRequest, staff_user_id: uuid.UUID
    ) -> StorefrontBackupCheckResponse:
        company_id, can_orders, can_refunds = await self._staff(staff_user_id)
        if not can_orders and not can_refunds:
            raise ForbiddenError("Backup checks are not available to this user")
        now = body.now or datetime.datetime.utcnow()
        manifest = {
            "backup_id": body.backup_id,
            "captured_at": body.captured_at,
            "credentials_included": body.credentials_included,
            "datasets": [
                {"name": item.name, "byte_size": item.byte_size, "sha256": item.sha256}
                for item in body.datasets
            ],
        }
        assessment = assess_backup(manifest, now)
        measured = measure_clocks(
            captured_at=body.captured_at,
            now=now,
            operator_started_at=body.operator_started_at,
            operator_finished_at=body.operator_finished_at,
        )
        alert_id: Optional[str] = None
        context: Optional[dict[str, object]] = None
        if assessment.alert is not None:
            async with unit_of_work(self.db):
                alert = await self.crud.add_alert(
                    StorefrontExceptionAlert(
                        company_id=company_id,
                        exception_id=None,
                        kind=assessment.alert.route,
                        queue_class=assessment.alert.queue_class,
                        context=assessment.alert.context,
                    )
                )
            alert_id = str(alert.id)
            context = assessment.alert.context
        return StorefrontBackupCheckResponse(
            ok=assessment.ok,
            code=assessment.code,
            message=assessment.message,
            proposal=proposal_model(),
            measured=measured,
            alert_id=alert_id,
            context=context,
        )

    async def raise_alert(
        self, body: StorefrontRecoveryAlertRequest, staff_user_id: uuid.UUID
    ) -> StorefrontExceptionAlertResponse:
        company_id, can_orders, can_refunds = await self._staff(staff_user_id)
        if not can_orders and not can_refunds:
            raise ForbiddenError("Recovery alerts are not available to this user")
        alert = route_alert(
            body.route,
            {"backup_id": body.backup_id, "dataset": body.dataset},
        )
        async with unit_of_work(self.db):
            stored = await self.crud.add_alert(
                StorefrontExceptionAlert(
                    company_id=company_id,
                    exception_id=None,
                    kind=alert.route,
                    queue_class=alert.queue_class,
                    context=alert.context,
                )
            )
        return StorefrontExceptionAlertResponse.model_validate(stored)

    async def _load(
        self, company_id: uuid.UUID, restore_id: str, *, ops_reachable: bool
    ) -> RecoveryState:
        rows = await self.crud.list_by_correlation(company_id, restore_correlation(restore_id))
        if not rows:
            raise NotFoundError("Restore recovery was not found")
        audits: list[StorefrontExceptionAudit] = []
        for row in rows:
            audits.extend(await self.crud.audits_for(row.id))
        return state_from_rows(
            restore_id,
            [RowView(seed_key=row.seed_key or "", status=row.status) for row in rows],
            [
                AuditView(
                    idempotency_key=audit.idempotency_key,
                    outcome=audit.outcome,
                    detail=audit.detail,
                )
                for audit in audits
            ],
            ops_reachable=ops_reachable,
        )

    def _response(self, state: RecoveryState) -> StorefrontRecoveryResponse:
        return StorefrontRecoveryResponse(
            restore_id=state.restore_id,
            correlation_id=restore_correlation(state.restore_id),
            checkout_allowed=state.checkout == "open",
            checkout="open" if state.checkout == "open" else "gated",
            reason=gate_reason(state),
            ops_reachable=state.ops_reachable,
            truths=dict(state.truths),
            effects=dict(state.effects),
            proposal=proposal_model(),
        )

    @staticmethod
    def _slots_for(
        body: StorefrontRecoveryOpenRequest, existing: list[StorefrontCommerceException]
    ) -> tuple[str, ...]:
        seeds = {row.seed_key or "" for row in existing}
        slots = ["order", "stock", "capacity"]
        if body.later_payment or any(seed.endswith(":payment") for seed in seeds):
            slots.insert(0, "payment")
        if body.later_refund or any(seed.endswith(":refund") for seed in seeds):
            slots.append("refund")
        return tuple(slots)

    @staticmethod
    def _truth_slots(state: RecoveryState, truth: str) -> tuple[str, ...]:
        if truth == "provider":
            slots: list[str] = []
            if state.later_payment:
                slots.append("payment")
            if state.later_refund:
                slots.append("refund")
            return tuple(slots)
        return (truth,)

    async def _staff(self, staff_user_id: uuid.UUID) -> tuple[uuid.UUID, bool, bool]:
        staff = await self.db.get(User, staff_user_id)
        if staff is None or staff.is_disabled or staff.role == "system":
            raise ForbiddenError("Storefront recovery is not available to this user")
        can_orders = await self.permissions.has_permission(staff_user_id, SALES_ORDERS)
        can_refunds = await self.permissions.has_permission(staff_user_id, SALES_REFUNDS)
        if not can_orders and not can_refunds:
            raise ForbiddenError("Storefront recovery is not available to this user")
        return staff.team_id, can_orders, can_refunds

    @staticmethod
    def _require_effect(effect: str, *, can_orders: bool, can_refunds: bool) -> None:
        if effect in _FINANCIAL_EFFECTS:
            if not can_refunds:
                raise ForbiddenError("Restricted financial recovery requires sales.refunds")
            return
        if not can_orders:
            raise ForbiddenError("Operational recovery requires sales.orders")

    @staticmethod
    def _require_truth(truth: str, *, can_orders: bool, can_refunds: bool) -> None:
        if truth == "provider":
            if not can_refunds:
                raise ForbiddenError("Provider reconciliation requires sales.refunds")
            return
        if not can_orders:
            raise ForbiddenError("Operational reconciliation requires sales.orders")

    @staticmethod
    def _raise_for_replay(outcome: str) -> None:
        if outcome == "needs_provider":
            raise ValidationError(
                "Payment success cannot be recorded without provider verification"
            )
        if outcome == "rejected":
            raise ValidationError("That effect is not part of this restore")

    @staticmethod
    def _raise_for_reconcile(outcome: str) -> None:
        if outcome == "needs_provider":
            raise ValidationError(
                "Payment success cannot be recorded without provider verification"
            )
        if outcome == "needs_effect":
            raise ValidationError("Reconcile only after the matching effect has been applied once")
        if outcome == "rejected":
            raise ValidationError("That truth is not part of this restore")
