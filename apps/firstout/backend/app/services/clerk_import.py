"""Explicit migration service; never invoked at startup or from webhooks."""

from __future__ import annotations

import asyncio
from typing import Protocol
from app.config import settings
from app.models.user import User


class ImportRateLimited(Exception):
    pass


class ClerkImportProvider(Protocol):
    async def create_user(self, payload: dict) -> str: ...
    async def ban_user(self, user_id: str) -> None: ...
    async def create_membership(self, org_id: str, user_id: str, role: str) -> None: ...


async def import_staff_user(
    user: User, org_id: str, provider: ClerkImportProvider, *, sleep=asyncio.sleep
) -> str:
    if not settings.clerk_import_enabled:
        raise RuntimeError("Clerk import is disabled")
    if user.role == "system" or user.email == "storefront-integration@system.example.com":
        raise ValueError("The storefront actor cannot become a Clerk staff user")
    if not user.password_hash.startswith(("$2a$", "$2b$")):
        raise ValueError("Unsupported password digest; retain legacy login")
    payload = {
        "external_id": str(user.id),
        "email_address": [user.email],
        "password_digest": user.password_hash,
        "password_hasher": "bcrypt",
        "create_organization_enabled": False,
    }
    clerk_id = user.clerk_user_id
    if not clerk_id:
        for attempt in range(5):
            try:
                clerk_id = await provider.create_user(payload)
                break
            except ImportRateLimited:
                if attempt == 4:
                    raise
                await sleep(min(2**attempt, 16))
    if user.is_disabled:
        await provider.ban_user(clerk_id)
    # Preserve richer local role grants; org:member is identity membership only.
    await provider.create_membership(org_id, clerk_id, "org:member")
    user.clerk_user_id = clerk_id
    return clerk_id
