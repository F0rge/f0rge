"""Compatibility endpoints reject local reset capabilities without consuming them."""

from __future__ import annotations

import hashlib

from fastapi import BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import PasswordResetConfirmRequest, PasswordResetMessage
from f0rge_core.exceptions import ValidationError


def hash_reset_token(token: str) -> str:
    """Historical format retained for inventory/verification, not token issuance."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PasswordResetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def request_reset(
        self, email: str, request: Request, background: BackgroundTasks
    ) -> PasswordResetMessage:
        raise ValidationError(
            "Use Clerk to recover your account; local password reset has been retired"
        )

    async def confirm_reset(
        self, body: PasswordResetConfirmRequest, request: Request
    ) -> PasswordResetMessage:
        raise ValidationError(
            "Use Clerk to recover your account; local password reset has been retired"
        )
