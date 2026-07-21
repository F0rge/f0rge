from __future__ import annotations

from typing import Optional

from mcp.server.auth.provider import AccessToken, TokenVerifier
from sqlalchemy import select

from app.mcp.database import make_main_session
from app.models.user_settings import UserSettings
from app.services.llm.encryption import hash_external_api_token
from f0rge_db.tenant import apply_service_role, clear_tenant_session


class BearerTokenVerifier(TokenVerifier):
    """Verify MCP Bearer tokens via O(1) hash lookup on user_settings."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        token_hash = hash_external_api_token(token)
        async with make_main_session() as db:
            try:
                await apply_service_role(db, "mcp_auth")
                result = await db.execute(
                    select(UserSettings).where(UserSettings.external_api_token_hash == token_hash)
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return None
                user_id = row.user_id
            finally:
                await db.rollback()
                await clear_tenant_session(db)

        return AccessToken(
            token=token,
            client_id=str(user_id),
            scopes=[],
        )
