"""Write a business change, its token audit entry and its replayable receipt atomically."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.mcp_operation import McpOperationCRUD
from app.exceptions import ForbiddenError
from app.models.mcp_operation import McpOperation
from app.models.mcp_token import McpToken
from app.services.mcp_action_types import Action
from app.services.mcp_tokens import McpTokenService
from app.services.permissions import PermissionService
from f0rge_core.exceptions import ConflictError, NotFoundError


def _receipt(op: McpOperation) -> dict[str, Any]:
    receipt = {
        "operation_id": str(op.id),
        "request_id": str(op.request_id),
        "action": op.action_name,
    }
    if op.completed_at is not None:
        return {**receipt, "status": "completed", "result": op.result}
    # Older servers saved proposed transfers before an employee confirmed them. A
    # retry may report that intent, but it must never turn a proposal into a stock movement.
    return {
        **receipt,
        "status": "not_executed",
        "message": (
            "This earlier request did not move stock. Do not retry it. "
            "If the user asks for a new change, call run_write with a new request ID."
        ),
    }


async def lookup_operation(
    db: AsyncSession,
    token: McpToken,
    request_id: uuid.UUID,
    *,
    actions: Iterable[Action],
) -> dict[str, Any]:
    op = await McpOperationCRUD(db, token.team_id, token.user_id).by_request(token, request_id)
    if op is None or token.version != op.token_version:
        raise NotFoundError("No operation found for this token and request ID")
    action = next((item for item in actions if item.name == op.action_name), None)
    if action is None or not await PermissionService(db).current_member_has_any(
        token.user_id, action.permissions
    ):
        raise ForbiddenError("You no longer have permission for this action")
    return _receipt(op)


async def execute_operation(
    db: AsyncSession,
    token: McpToken,
    action: Action,
    args: BaseModel,
    request_id: uuid.UUID,
) -> dict[str, Any]:
    """Caller authenticates and holds the token row lock and unit of work through commit."""
    if action.effect != "write":
        raise ConflictError("This action cannot make a change")
    values = args.model_dump(mode="json")
    operations = McpOperationCRUD(db, token.team_id, token.user_id)
    previous = await operations.by_request(token, request_id)
    audit = McpTokenService(db, token.team_id)
    if previous is not None:
        if (previous.action_name, previous.arguments, previous.token_version) != (
            action.name,
            values,
            token.version,
        ):
            raise ConflictError("This request ID was already used for a different change")
        audit.record(
            token,
            "write_replayed",
            "mcp",
            action_name=action.name,
            operation_id=previous.id,
        )
        return _receipt(previous)
    op = McpOperation(
        team_id=token.team_id,
        user_id=token.user_id,
        token_id=token.id,
        token_version=token.version,
        request_id=request_id,
        action_name=action.name,
        arguments=values,
    )
    op.result = await action.handler(db, token, args)
    op.completed_at = datetime.now(UTC)
    await operations.add_and_flush(op)
    audit.record(token, "write_requested", "mcp", action_name=action.name, operation_id=op.id)
    return _receipt(op)
