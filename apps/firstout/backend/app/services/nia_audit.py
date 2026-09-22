from __future__ import annotations

import copy
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.nia import NiaThreadCRUD
from app.crud.nia_audit import NiaAuditCRUD
from app.models.nia import NiaAuditEvent
from app.permissions import STOCK_COST_VIEW
from app.schemas.nia import NiaAuditEventResponse
from app.services.permissions import PermissionService
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work


def extract_tool_args(
    agent_messages: Optional[list[Any]],
    tool_call_id: Optional[str],
) -> Optional[dict[str, Any]]:
    if not agent_messages or not tool_call_id:
        return None
    for message in agent_messages:
        if not isinstance(message, dict):
            continue
        parts = message.get("parts") or []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if part.get("tool_call_id") == tool_call_id:
                args = part.get("args")
                if isinstance(args, dict):
                    return copy.deepcopy(args)
    return None


def redact_cost_args(
    args: Optional[dict[str, Any]],
    *,
    hide_cost: bool,
) -> Optional[dict[str, Any]]:
    if args is None or not hide_cost:
        return args

    def _redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: None if key == "unit_cost_zar" or "cost" in key.lower() else _redact(nested)
                for key, nested in value.items()
            }
        if isinstance(value, list):
            return [_redact(item) for item in value]
        return value

    return _redact(copy.deepcopy(args))


class NiaAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = NiaAuditCRUD(db)
        self.thread_crud = NiaThreadCRUD(db)
        self.permissions = PermissionService(db)

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        tool_name: str,
        args: Optional[dict[str, Any]],
        decision: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
    ) -> None:
        event = NiaAuditEvent(
            user_id=user_id,
            thread_id=thread_id,
            tool_name=tool_name,
            args=args,
            decision=decision,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(event)

    async def list_for_thread(
        self,
        thread_id: uuid.UUID,
        viewer_user_id: uuid.UUID,
    ) -> list[NiaAuditEventResponse]:
        thread = await self.thread_crud.get_owned(thread_id, viewer_user_id)
        if thread is None:
            raise NotFoundError("Thread not found")
        hide_cost = not await self.permissions.has_permission(viewer_user_id, STOCK_COST_VIEW)
        rows = await self.crud.list_for_thread(thread_id)
        return [
            NiaAuditEventResponse(
                id=row.id,
                user_id=row.user_id,
                thread_id=row.thread_id,
                tool_name=row.tool_name,
                args=redact_cost_args(row.args, hide_cost=hide_cost),
                decision=row.decision,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                created_at=row.created_at,
            )
            for row in rows
        ]
