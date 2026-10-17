"""Static bearer token. The process refuses to start when BUYCYCLE_MCP_TOKEN is unset."""

from __future__ import annotations

import os
import secrets
import sys
from typing import Optional

from mcp.server.auth.provider import AccessToken, TokenVerifier


def require_token() -> str:
    token = os.environ.get("BUYCYCLE_MCP_TOKEN", "").strip()
    if not token:
        print("BUYCYCLE_MCP_TOKEN is unset; refusing to start", file=sys.stderr)
        raise SystemExit(1)
    return token


class BearerTokenVerifier(TokenVerifier):
    """Accept only the single configured bearer token."""

    def __init__(self, expected: str) -> None:
        self._expected = expected

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        if not token or not secrets.compare_digest(token, self._expected):
            return None
        return AccessToken(token=token, client_id="buycycle", scopes=[])
