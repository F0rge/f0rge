"""Durable per-record outcomes; domain commits include their batch checkpoint."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import Membership
from app.models.record_workspace import RecordWorkspaceBatch
from app.models.team import Team
from app.models.user import User
from app.schemas.record_workspace import WorkspaceExecute, WorkspaceExecuteResponse
from app.services.record_workspace import RecordWorkspaceService
from app.services.record_workspace_actions import apply_action
from app.services.record_workspace_filters import label, payload_hash, revision
from app.services.record_workspace_registry import DEFINITIONS
from app.services.record_workspace_tokens import read_token
from f0rge_core.exceptions import ConflictError, DomainError, ValidationError
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx


class RecordWorkspaceExecuteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.workspace = RecordWorkspaceService(db)

    async def _team_lock(self):
        await self.db.execute(
            select(Team.id).where(Team.id == tenant_id_ctx.get()).with_for_update()
        )

    async def _batch(self, request_id: uuid.UUID, actor: uuid.UUID):
        return await self.db.scalar(
            select(RecordWorkspaceBatch)
            .where(
                RecordWorkspaceBatch.team_id == tenant_id_ctx.get(),
                RecordWorkspaceBatch.actor_user_id == actor,
                RecordWorkspaceBatch.request_id == request_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def _lock_record(self, resource: str, record_id: uuid.UUID):
        model = DEFINITIONS[resource].model
        statement = select(model.id).where(model.id == record_id)
        if model is User:
            statement = statement.where(
                User.id.in_(
                    select(Membership.user_id).where(Membership.team_id == tenant_id_ctx.get())
                )
            )
        else:
            statement = statement.where(model.team_id == tenant_id_ctx.get())
        return await self.db.scalar(statement.with_for_update())

    async def execute(
        self, resource: str, body: WorkspaceExecute, actor: uuid.UUID
    ) -> WorkspaceExecuteResponse:
        claims = read_token(body.preflight_token, "preflight", resource, actor)
        action, patch, ids = claims["action"], claims["patch"], claims["ids"]
        await self.workspace.require_access(resource, actor, action, patch)
        await self.workspace.require_access(resource, actor)
        if not ids:
            raise ValidationError("No eligible records were selected")
        digest = payload_hash(
            {
                "resource": resource,
                "action": action,
                "patch": patch,
                "ids": ids,
                "revisions": claims["revisions"],
            }
        )
        await self._team_lock()
        batch = await self._batch(body.request_id, actor)
        replayed = batch is not None
        if batch is None:
            batch = RecordWorkspaceBatch(
                actor_user_id=actor,
                request_id=body.request_id,
                resource=resource,
                action=action,
                payload_hash=digest,
                selection=[{"id": value, "revision": claims["revisions"][value]} for value in ids],
                result={"succeeded": [], "failed": []},
            )
            async with unit_of_work(self.db):
                self.db.add(batch)
        elif batch.payload_hash != digest or batch.resource != resource:
            raise ConflictError("This request ID was already used for different changes")
        for record_id in ids:
            self.db.expire_all()
            await self._team_lock()
            batch = await self._batch(body.request_id, actor)
            result = batch.result
            done = set(result["succeeded"]) | {item["id"] for item in result["failed"]}
            if record_id in done:
                continue
            record_label = "Unavailable record"
            try:
                if await self._lock_record(resource, uuid.UUID(record_id)) is None:
                    raise ConflictError("Record is no longer available")
                row = await self.workspace.row(resource, uuid.UUID(record_id))
                record_label = label(row)
                if revision(row) != claims["revisions"][record_id]:
                    raise ConflictError("Record changed after review; refresh and review again")
                await self.workspace.require_access(resource, actor, action, patch)
                reason = await self.workspace.eligibility(resource, action, row, len(ids), patch)
                if reason:
                    raise ConflictError(reason)
                # The called domain method commits once its validation and mutation succeed.
                # Staging this outcome first makes that same commit its durable checkpoint.
                batch.result = {
                    "succeeded": result["succeeded"] + [record_id],
                    "failed": result["failed"],
                }
                await apply_action(self.db, resource, action, uuid.UUID(record_id), patch, actor)
                async with unit_of_work(self.db):
                    pass
            except (DomainError, IntegrityError) as exc:
                await self.db.rollback()
                await self._team_lock()
                batch = await self._batch(body.request_id, actor)
                current = batch.result
                # A domain response reload may fail after its mutation and checkpoint
                # committed. Keep that durable success instead of reporting both outcomes.
                if record_id in current["succeeded"]:
                    continue
                batch.result = {
                    "succeeded": current["succeeded"],
                    "failed": current["failed"]
                    + [
                        {
                            "id": record_id,
                            "label": record_label,
                            "reason": exc.detail
                            if isinstance(exc, DomainError)
                            else "Record is linked to other data or violates a constraint",
                        },
                    ],
                }
                async with unit_of_work(self.db):
                    pass
        batch = await self._batch(body.request_id, actor)
        return WorkspaceExecuteResponse(
            request_id=body.request_id, replayed=replayed, **batch.result
        )
