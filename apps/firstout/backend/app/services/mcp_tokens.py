from __future__ import annotations

import hmac
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.mcp_token import McpTokenCRUD
from app.exceptions import ForbiddenError, McpTokensUnconfiguredError
from app.models.mcp_token import McpToken, McpTokenActivity
from app.schemas.mcp_token import (
    McpAccessResponse,
    McpTokenActivityResponse,
    McpTokenCreate,
    McpTokenIssued,
    McpTokenResponse,
)
from app.services.record_workspace_tokens import signing_key
from f0rge_core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from f0rge_db.crud import unit_of_work

_RECENT_ACTIVITY_LIMIT = 30
_PERSONAL_TOKEN = re.compile(r"fo_mcp_([0-9a-f]{32})_[A-Za-z0-9_-]{43}\Z")


def mcp_signing_key() -> Optional[bytes]:
    key = settings.mcp_token_signing_key or signing_key()
    if key is None:
        return None
    return hmac.digest(key.encode(), b"firstout:mcp-personal-tokens:v1", "sha256")


def parse_credential(secret: str) -> Optional[tuple[uuid.UUID, str]]:
    if not settings.clerk_enabled or settings.tenant_isolation_mode != "enforced":
        return None
    match = _PERSONAL_TOKEN.fullmatch(secret)
    key = mcp_signing_key()
    if match is None or key is None:
        return None
    # The locator selects the RLS scope, while only a matching digest can authenticate.
    return uuid.UUID(hex=match[1]), hmac.digest(key, secret.encode(), "sha256").hex()


class McpTokenService:
    def __init__(self, db: AsyncSession, team_id: uuid.UUID) -> None:
        self.db = db
        self.team_id = team_id
        self.crud = McpTokenCRUD(db, team_id)

    async def list(self, user_id: uuid.UUID) -> McpAccessResponse:
        tokens = await self.crud.tokens(user_id)
        activity = await self.crud.recent_activity(user_id, _RECENT_ACTIVITY_LIMIT)
        return McpAccessResponse(
            endpoint=str(settings.mcp_public_url),
            tokens=[McpTokenResponse.model_validate(token) for token in tokens],
            activity=[McpTokenActivityResponse.model_validate(event) for event in activity],
        )

    async def create(self, user_id: uuid.UUID, data: McpTokenCreate) -> McpTokenIssued:
        async with unit_of_work(self.db):
            # Serialize creation for this member so a concurrent request cannot claim the same name.
            if await self.crud.active_clerk_identity(user_id, for_update=True) is None:
                raise UnauthorizedError("Active staff membership is required")
            now = datetime.now(UTC)
            if await self.crud.active_name_exists(user_id, data.name, now):
                raise ConflictError("An active token already uses this name")
            token = McpToken(
                team_id=self.team_id,
                user_id=user_id,
                name=data.name,
                expires_at=now + timedelta(days=data.expires_in_days),
            )
            secret = self._replace_secret(token)
            await self.crud.add_and_flush(token)
            self.record(token, "generated", "firstout")
        return McpTokenIssued(token=McpTokenResponse.model_validate(token), secret=secret)

    async def rotate(self, user_id: uuid.UUID, token_id: uuid.UUID, version: int) -> McpTokenIssued:
        async with unit_of_work(self.db):
            token = await self._lock_owned(user_id, token_id)
            if token.status != "active" or token.version != version:
                raise ConflictError("This token changed. Refresh before replacing it.")
            secret = self._replace_secret(token)
            token.version += 1
            token.last_used_at = None
            self.record(token, "rotated", "firstout")
        return McpTokenIssued(token=McpTokenResponse.model_validate(token), secret=secret)

    async def revoke(self, user_id: uuid.UUID, token_id: uuid.UUID) -> None:
        async with unit_of_work(self.db):
            token = await self._lock_owned(user_id, token_id)
            if token.revoked_at is None:
                token.revoked_at = datetime.now(UTC)
                token.digest = None
                self.record(token, "revoked", "firstout")

    async def clerk_identity_for_token(self, digest: str) -> Optional[tuple[str, str]]:
        token = await self.crud.find_for_authentication(digest)
        if token is None or token.status != "active":
            return None
        return await self.crud.active_clerk_identity(token.user_id)

    async def authenticate(
        self, digest: str, clerk_identity: tuple[str, str]
    ) -> Optional[McpToken]:
        """The caller keeps the token row locked until its authenticated action commits."""
        token = await self.crud.find_for_authentication(digest, for_update=True)
        if token is None or token.status != "active":
            return None
        if await self.crud.active_clerk_identity(token.user_id) != clerk_identity:
            return None
        token.last_used_at = datetime.now(UTC)
        return token

    def record(self, token: McpToken, action: str, source: str, result: str = "success") -> None:
        self.crud.add(
            McpTokenActivity(
                team_id=self.team_id,
                user_id=token.user_id,
                token_id=token.id,
                token_name=token.name,
                action=action,
                source=source,
                result=result,
                occurred_at=datetime.now(UTC),
            )
        )

    async def _lock_owned(self, user_id: uuid.UUID, token_id: uuid.UUID) -> McpToken:
        token = await self.crud.lock_owned(user_id, token_id)
        if token is None:
            raise NotFoundError("MCP token not found")
        if await self.crud.active_clerk_identity(user_id) is None:
            raise ForbiddenError("Active staff membership is required")
        return token

    def _replace_secret(self, token: McpToken) -> str:
        key = mcp_signing_key()
        if key is None or not settings.clerk_secret_key:
            raise McpTokensUnconfiguredError()
        secret = f"fo_mcp_{self.team_id.hex}_{secrets.token_urlsafe(32)}"
        token.suffix = secret[-4:]
        token.digest = hmac.digest(key, secret.encode(), "sha256").hex()
        return secret
