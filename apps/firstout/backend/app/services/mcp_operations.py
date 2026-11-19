"""Write receipts belong to one employee, business and personal token generation."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.mcp_operation import McpOperationCRUD
from app.crud.mcp_token import McpTokenCRUD
from app.crud.user import TeamCRUD
from app.exceptions import ForbiddenError, McpTokensUnconfiguredError
from app.models.mcp_operation import McpOperation
from app.models.mcp_token import McpToken
from app.services.clerk_api import ClerkAPI
from app.services.mcp_action_types import Action
from app.services.mcp_tokens import McpTokenService, mcp_signing_key
from app.services.mcp_transfers import TRANSFER_ACTIONS, preview_transfer
from app.services.permissions import PermissionService
from app.services.tenant_signup import organisation_url
from f0rge_db.crud import unit_of_work
from f0rge_core.exceptions import (
    DomainError,
    ConflictError,
    ExternalServiceError,
    GoneError,
    NotFoundError,
)

_REVIEW_LIFETIME = timedelta(minutes=10)


def _receipt(op: McpOperation) -> dict[str, Any]:
    receipt = {
        "operation_id": str(op.id),
        "request_id": str(op.request_id),
        "action": op.action_name,
    }
    if op.completed_at is not None:
        return {**receipt, "status": "completed", "result": op.result}
    if op.expires_at is None or op.expires_at <= datetime.now(UTC):
        return {**receipt, "status": "expired"}
    origin = organisation_url().rstrip("/")
    return {
        **receipt,
        "status": "awaiting_confirmation",
        "expires_at": op.expires_at.isoformat(),
        "review_url": f"{origin}/settings/integrations/mcp-tokens/review/{op.id}",
    }


async def _require_action(
    db: AsyncSession, user_id: uuid.UUID, name: str, actions: Iterable[Action]
) -> Action:
    action = next((action for action in actions if action.name == name), None)
    if action is None or not await PermissionService(db).current_member_has_any(
        user_id, action.permissions
    ):
        raise ForbiddenError("You no longer have permission for this action")
    return action


async def lookup_operation(
    db: AsyncSession,
    token: McpToken,
    request_id: uuid.UUID,
    *,
    actions: Iterable[Action] = TRANSFER_ACTIONS,
) -> dict[str, Any]:
    op = await McpOperationCRUD(db, token.team_id, token.user_id).by_request(token, request_id)
    if op is None or token.version != op.token_version:
        raise NotFoundError("No operation found for this token and request ID")
    await _require_action(db, token.user_id, op.action_name, actions)
    return _receipt(op)


async def request_operation(
    db: AsyncSession,
    token: McpToken,
    action: Action,
    args: BaseModel,
    request_id: uuid.UUID,
) -> dict[str, Any]:
    """Caller authenticates and holds the token row lock and unit of work through commit."""
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
    if action.effect == "review":
        op.preview = await preview_transfer(db, token, action.name, args)
        op.expires_at = min(token.expires_at, datetime.now(UTC) + _REVIEW_LIFETIME)
    elif action.effect == "write":
        op.result = await action.handler(db, token, args)
        op.completed_at = datetime.now(UTC)
    else:
        raise ConflictError("This action cannot request a change")
    await operations.add_and_flush(op)
    audit.record(token, "write_requested", "mcp", action_name=action.name, operation_id=op.id)
    return _receipt(op)


async def staff_review(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    operation_id: uuid.UUID,
    provider: ClerkAPI,
    *,
    confirm: bool = False,
) -> dict[str, Any]:
    """A signed-in employee reviews their own immutable request in the selected business."""
    operations = McpOperationCRUD(db, team_id, user_id)
    token_id = await operations.review_token(operation_id)
    if token_id is None:
        raise NotFoundError("Review request not found for your account in this business")
    tokens = McpTokenCRUD(db, team_id)
    identity = await tokens.active_clerk_identity(user_id)
    if identity is None:
        raise ForbiddenError("Active staff membership is required")
    if (
        not settings.clerk_enabled
        or settings.tenant_isolation_mode != "enforced"
        or mcp_signing_key() is None
    ):
        raise McpTokensUnconfiguredError()
    # Check the provider before taking the same token lock used for rotation and MCP calls.
    try:
        async with asyncio.timeout(5):
            active = await provider.staff_access_active(*identity)
    except (TimeoutError, ConflictError, ExternalServiceError) as exc:
        raise McpTokensUnconfiguredError() from exc
    if not active:
        raise ForbiddenError("Active staff membership is required")
    token = await tokens.lock_owned(user_id, token_id)
    if confirm:
        # Staff and role edits take the conflicting directory lock. Other reviewers may proceed.
        await TeamCRUD(db).lock_current(shared=True)
    if (
        token is None
        or token.status != "active"
        or await tokens.active_clerk_identity(user_id) != identity
    ):
        raise ForbiddenError("The token or staff membership is no longer active")
    op = await operations.review(operation_id)
    if token.version != op.token_version:
        raise ForbiddenError("This token was replaced. Request the action again.")
    action = await _require_action(db, user_id, op.action_name, TRANSFER_ACTIONS)
    if action.effect != "review":
        raise ConflictError("This action no longer supports confirmation")
    if confirm and op.completed_at is None:
        if not settings.mcp_writes_enabled:
            raise ForbiddenError("MCP writes are paused. This request cannot be confirmed.")
        if op.expires_at is None or op.expires_at <= datetime.now(UTC):
            raise GoneError("This review expired. Request the action again.")
        args = action.arguments.model_validate(op.arguments)
        # The transfer lock acquired by preview_transfer is held through the write and receipt.
        if await preview_transfer(db, token, action.name, args) != op.preview:
            raise ConflictError("The transfer changed. Request a new review before continuing.")
        if op.expires_at <= datetime.now(UTC):
            raise GoneError("This review expired. Request the action again.")
        op.result = await action.handler(db, token, args)
        op.confirmed_by = user_id
        op.completed_at = datetime.now(UTC)
        McpTokenService(db, team_id).record(
            token,
            "write_confirmed",
            "firstout",
            action_name=action.name,
            operation_id=op.id,
        )
    return {**_receipt(op), "preview": op.preview, "token_name": token.name}


async def confirm_staff_review(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    operation_id: uuid.UUID,
    provider: ClerkAPI,
) -> dict[str, Any]:
    async with unit_of_work(db):
        try:
            # An unsuccessful domain write must roll back before recording its outcome.
            async with db.begin_nested():
                return await staff_review(
                    db, team_id, user_id, operation_id, provider, confirm=True
                )
        except DomainError as exc:
            operations = McpOperationCRUD(db, team_id, user_id)
            token_id = await operations.review_token(operation_id)
            if token_id is None:
                raise
            token = await McpTokenCRUD(db, team_id).lock_owned(user_id, token_id)
            if token is None:
                raise
            op = await operations.review(operation_id)
            outcome = "denied" if isinstance(exc, ForbiddenError) else "failed"
            McpTokenService(db, team_id).record(
                token,
                "write_confirmed",
                "firstout",
                outcome,
                action_name=op.action_name,
                operation_id=op.id,
            )
            failure = exc
    raise failure
