"""Replayable receipts for MCP writes.

A hand-written action commits its change, audit entry and receipt together. A route action
commits a started receipt first, runs the API route in the route's own transaction, then
records the outcome. A request ID is therefore single-use for a route action, and only a
digest of its arguments is kept.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.mcp_operation import McpOperationCRUD
from app.exceptions import ForbiddenError
from app.models.mcp_operation import McpOperation
from app.models.mcp_token import McpToken
from app.services.mcp_action_types import Action
from app.services.mcp_route_runner import RouteOutcome
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
    state = (op.result or {}).get("state")
    if state == "failed":
        return {
            **receipt,
            "status": "failed",
            "message": f"{op.result['message']} To try again, call run_write with a new request ID.",
        }
    if state == "started":
        # The route may have committed its change before the outcome could be saved.
        return {
            **receipt,
            "status": "unknown",
            "message": (
                "This request was started and its outcome was not recorded. It may still be "
                "running, so look it up again. If it stays unknown, check the record in "
                "Firstout before retrying with a new request ID."
            ),
        }
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


async def _replayed(
    operations: McpOperationCRUD,
    audit: McpTokenService,
    token: McpToken,
    action: Action,
    values: dict[str, Any],
    request_id: uuid.UUID,
) -> dict[str, Any] | None:
    previous = await operations.by_request(token, request_id)
    if previous is None:
        return None
    if (previous.action_name, previous.arguments, previous.token_version) != (
        action.name,
        values,
        token.version,
    ):
        raise ConflictError("This request ID was already used for a different change")
    audit.record(token, "write_replayed", "mcp", action_name=action.name, operation_id=previous.id)
    return _receipt(previous)


async def begin_route_operation(
    db: AsyncSession,
    token: McpToken,
    action: Action,
    args: BaseModel,
    request_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Save the started receipt and audit entry that the caller commits before the route runs.

    Returns the recorded receipt when this request ID was already used, and the route must
    then not run.
    """
    # Unset fields stay unset: a PATCH that omits a field differs from one that clears it.
    values = args.model_dump(mode="json", exclude_unset=True)
    # The body may hold contact details, prices or journal lines. Only a digest is kept, to
    # tell a retry from a different change, with the path values that name the record.
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"))
    values = {
        "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "path": {name: values[name] for name in action.route.path_params},
    }
    operations = McpOperationCRUD(db, token.team_id, token.user_id)
    audit = McpTokenService(db, token.team_id)
    replayed = await _replayed(operations, audit, token, action, values, request_id)
    if replayed is not None:
        return replayed
    op = McpOperation(
        team_id=token.team_id,
        user_id=token.user_id,
        token_id=token.id,
        token_version=token.version,
        request_id=request_id,
        action_name=action.name,
        arguments=values,
        result={"state": "started"},
    )
    try:
        async with db.begin_nested():
            await operations.add_and_flush(op)
    except IntegrityError:
        # The token row lock normally serialises calls. The unique request still decides.
        replayed = await _replayed(operations, audit, token, action, values, request_id)
        if replayed is None:
            raise
        return replayed
    # Neutral until the route answers. finish_route_operation records the one outcome.
    audit.record(
        token, "write_requested", "mcp", "started", action_name=action.name, operation_id=op.id
    )
    return None


async def finish_route_operation(
    db: AsyncSession, token: McpToken, request_id: uuid.UUID, outcome: RouteOutcome
) -> dict[str, Any]:
    """Record what the route answered. Without an answer the receipt stays started."""
    op = await McpOperationCRUD(db, token.team_id, token.user_id).by_request(token, request_id)
    if op is None:
        raise NotFoundError("No operation found for this token and request ID")
    if outcome.audit == "success":
        op.result = outcome.receipt
        op.completed_at = datetime.now(UTC)
    elif outcome.status is not None:
        op.result = {
            "state": "failed",
            "http_status": outcome.status,
            "message": outcome.error,
        }
    McpTokenService(db, token.team_id).record(
        token,
        "write_requested",
        "mcp",
        outcome.audit if outcome.status is not None else "unknown",
        action_name=op.action_name,
        operation_id=op.id,
    )
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
    audit = McpTokenService(db, token.team_id)
    replayed = await _replayed(operations, audit, token, action, values, request_id)
    if replayed is not None:
        return replayed
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
