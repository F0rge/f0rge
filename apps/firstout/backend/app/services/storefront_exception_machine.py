from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.storefront_exceptions import StorefrontExceptionCRUD
from app.models.storefront_commerce_exception import (
    StorefrontCommerceException,
    StorefrontExceptionAudit,
    StorefrontExceptionProjection,
)
from app.schemas.storefront_exceptions import (
    StorefrontExceptionCommandList,
    StorefrontExceptionCommandResponse,
    StorefrontExceptionCommandResult,
    StorefrontExceptionCommandResultResponse,
    StorefrontExceptionObservations,
    StorefrontExceptionScanResponse,
)
from app.services.ops_commerce import OpsCommerceService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


SOURCE_FRESHNESS = datetime.timedelta(minutes=5)


class StorefrontExceptionMachineService:
    """Commerce reports complete source scans; operators authorize durable actions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = StorefrontExceptionCRUD(db)

    async def authorize(
        self, *, authorization: Optional[str], requested_company: Optional[str], request_host: str
    ) -> uuid.UUID:
        return await OpsCommerceService(self.db)._authorize(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )

    async def observe(
        self, body: StorefrontExceptionObservations, company_id: uuid.UUID
    ) -> StorefrontExceptionScanResponse:
        observed_at = body.observed_at.replace(tzinfo=None)
        received_at = datetime.datetime.utcnow()
        if observed_at > received_at:
            raise ValidationError("Source scan time is in the future")
        if received_at - observed_at > SOURCE_FRESHNESS:
            raise ValidationError("Source scan is older than the freshness window")
        accepted = False
        async with unit_of_work(self.db):
            watermark = await self.crud.lock_projection(company_id)
            if watermark is None or observed_at > watermark.observed_at:
                accepted = True
                rows = await self.crud.list_live(company_id)
                by_identity = {(row.kind, row.correlation_id): row for row in rows}
                present = set()
                for observation in body.observations:
                    identity = (observation.kind, observation.correlation_id)
                    present.add(identity)
                    row = by_identity.get(identity)
                    if row is None:
                        row = StorefrontCommerceException(
                            company_id=company_id,
                            source="commerce",
                            kind=observation.kind,
                            correlation_id=observation.correlation_id,
                            detected_at=observation.detected_at.replace(tzinfo=None),
                        )
                        self.db.add(row)
                    row.status = observation.status
                    row.explanation = observation.explanation
                    row.safe_action = observation.safe_action
                    row.last_error = observation.last_error
                    row.amount_minor = observation.amount_minor
                    row.payment_reference = observation.payment_reference
                    row.provider_verified = observation.provider_verified
                    row.blocks_checkout = observation.blocks_checkout
                    row.source_received_at = received_at
                    row.resolved_at = None
                    row.effect_applied = False
                for identity, row in by_identity.items():
                    if identity not in present:
                        row.status = "resolved"
                        row.resolved_at = row.resolved_at or received_at
                        row.blocks_checkout = False
                        row.source_received_at = received_at
                if watermark is None:
                    self.db.add(
                        StorefrontExceptionProjection(
                            company_id=company_id, observed_at=observed_at, received_at=received_at
                        )
                    )
                else:
                    watermark.observed_at = observed_at
                    watermark.received_at = received_at
        blocking = await self.crud.blocking_open(company_id)
        return StorefrontExceptionScanResponse(accepted=accepted, checkout_allowed=not blocking)

    async def commands(
        self, company_id: uuid.UUID, limit: int = 100
    ) -> StorefrontExceptionCommandList:
        rows = await self.crud.list_commands(company_id, limit)
        return StorefrontExceptionCommandList(
            items=[
                StorefrontExceptionCommandResponse(
                    id=command.id,
                    correlation_id=row.correlation_id,
                    kind=row.kind,
                    action=command.action,
                    idempotency_key=command.idempotency_key,
                )
                for command, row in rows
            ]
        )

    async def result(
        self, command_id: uuid.UUID, body: StorefrontExceptionCommandResult, company_id: uuid.UUID
    ) -> StorefrontExceptionCommandResultResponse:
        async with unit_of_work(self.db):
            command = await self.crud.get_command(command_id, company_id)
            if command is None:
                raise NotFoundError("Commerce repair command not found")
            # Staff requests and worker results both lock exception before command.
            row = await self.crud.get_by_id(command.exception_id, for_update=True)
            if row is None or row.source != "commerce" or row.company_id != company_id:
                raise NotFoundError("Commerce exception not found")
            command = await self.crud.get_command(command_id, company_id, for_update=True)
            if command is None:
                raise NotFoundError("Commerce repair command not found")
            if command.status != "pending":
                if command.status != body.outcome or command.detail != body.detail:
                    raise ConflictError(
                        "Repair result identity was already used for another outcome"
                    )
                return StorefrontExceptionCommandResultResponse(id=command.id, outcome=body.outcome)
            projection = await self.crud.get_projection(company_id)
            if body.outcome == "repaired" and (
                row.status != "resolved"
                or row.source_received_at is None
                or row.source_received_at < command.created_at
                or projection is None
                or projection.observed_at < command.created_at
                or datetime.datetime.utcnow() - projection.observed_at > SOURCE_FRESHNESS
            ):
                raise ConflictError("A fresh complete source scan must verify repair convergence")
            audit = await self.crud.get_audit(command.audit_id)
            if audit is None:
                raise NotFoundError("Commerce repair authorization not found")
            command.status = body.outcome
            command.detail = body.detail
            command.completed_at = datetime.datetime.utcnow()
            row.repair_pending = False
            if body.outcome == "repaired":
                row.effect_applied = True
                row.repair_count += 1
            await self.crud.add_audit(
                StorefrontExceptionAudit(
                    exception_id=row.id,
                    actor_user_id=audit.actor_user_id,
                    idempotency_key=f"command:{command.id}",
                    reason=audit.reason,
                    outcome="repaired" if body.outcome == "repaired" else "repair_failed",
                    detail=body.detail,
                )
            )
        return StorefrontExceptionCommandResultResponse(id=command_id, outcome=body.outcome)
