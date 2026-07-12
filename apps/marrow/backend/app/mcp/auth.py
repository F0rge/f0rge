from __future__ import annotations

import secrets
from typing import Optional

from mcp.server.auth.provider import AccessToken, TokenVerifier
from sqlalchemy import select

from app.mcp.database import make_main_session
from app.models.user_settings import UserSettings
from app.services.llm.encryption import decrypt
from f0rge_db.tenant import apply_service_role


class BearerTokenVerifier(TokenVerifier):
    """Verify MCP Bearer tokens against each user's encrypted external API token."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        async with make_main_session() as db:
            await apply_service_role(db, "mcp_auth")
            rows = (await db.execute(select(UserSettings))).scalars().all()

        for row in rows:
            if row.external_api_token_encrypted is None:
                continue

            try:
                stored_plaintext = decrypt(row.external_api_token_encrypted)
            except Exception:
                continue

            if secrets.compare_digest(token, stored_plaintext):
                return AccessToken(
                    token=token,
                    client_id=str(row.user_id),
                    scopes=[],
                )

        return None
