from __future__ import annotations

import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.mcp.database import make_main_session
from app.services.llm.encryption import decrypt
from app.services.llm.factory import load_user_settings_singleton


class BearerTokenVerifier(TokenVerifier):
    """Verifies incoming Bearer tokens against the encrypted token stored in user_settings.

    Uses secrets.compare_digest to prevent timing attacks. Never logs the token or key.
    For stdio transport this verifier is never instantiated — auth is implicit via SSH/exec.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        async with make_main_session() as db:
            row = await load_user_settings_singleton(db)

        if row is None or row.external_api_token_encrypted is None:
            return None

        try:
            stored_plaintext = decrypt(row.external_api_token_encrypted)
        except Exception:
            # Decryption failure (wrong key, corrupt data) → deny access.
            return None

        if not secrets.compare_digest(token, stored_plaintext):
            return None

        return AccessToken(
            token=token,
            client_id="external",
            scopes=[],
        )
