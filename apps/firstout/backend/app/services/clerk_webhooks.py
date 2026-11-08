"""Signed, replay-safe events trigger canonical provider membership reconciliation."""

from __future__ import annotations

import json

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import settings
from app.models.clerk_webhook_event import ClerkWebhookEvent
from app.models.membership import Membership
from app.models.team import Team
from app.models.user import User
from app.services.clerk_api import ClerkAPI
from app.services.tenant_signup import TenantSignupService
from f0rge_db.crud import unit_of_work


def verify_webhook(payload: bytes, headers: dict[str, str]) -> dict:
    if not settings.clerk_webhook_secret:
        raise HTTPException(503, "Webhook verification unavailable")
    try:
        Webhook(settings.clerk_webhook_secret).verify(payload, headers)
        event = json.loads(payload)
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError("Invalid event")
        return event
    except (WebhookVerificationError, ValueError) as exc:
        raise HTTPException(400, "Invalid webhook signature") from exc


class ClerkWebhookService:
    def __init__(self, db: AsyncSession, provider: ClerkAPI) -> None:
        self.db = db
        self.provider = provider

    async def receive(self, request: Request) -> dict:
        # Check Content-Length early; bounded streaming also covers chunked bodies.
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 1_000_000:
                raise HTTPException(413, "Webhook too large")
            chunks.append(chunk)
        payload = b"".join(chunks)
        event = verify_webhook(payload, dict(request.headers))
        event_id = request.headers["svix-id"]
        async with unit_of_work(self.db):
            result = await self.db.execute(
                insert(ClerkWebhookEvent)
                .values(svix_id=event_id, event_type=event["type"])
                .on_conflict_do_nothing()
                .returning(ClerkWebhookEvent.svix_id)
            )
            if result.scalar_one_or_none() is None:
                return {"status": "duplicate"}
            if not settings.clerk_webhook_reconcile_enabled:
                return {"status": "quarantined"}
            if settings.tenant_isolation_mode != "enforced" or not settings.clerk_enabled:
                raise HTTPException(503, "Clerk reconciliation requires enforced tenancy")
            await self._reconcile(event)
        return {"status": "processed"}

    async def _reconcile(self, event: dict) -> None:
        if not event["type"].startswith("organizationMembership."):
            return  # Identity-directory linking is always an explicit operator action.
        data = event.get("data") or {}
        subject = data.get("public_user_data", {}).get("user_id")
        org_id = data.get("organization", {}).get("id")
        if not isinstance(subject, str) or not isinstance(org_id, str):
            return
        team = await self.db.scalar(select(Team).where(Team.clerk_org_id == org_id))
        if team is None:
            return
        # Old/out-of-order events never determine current membership or role.
        canonical = await self.provider.membership(org_id, subject)
        user = await self.db.scalar(select(User).where(User.clerk_user_id == subject))
        existing = (
            None
            if user is None
            else await self.db.scalar(
                select(Membership)
                .where(Membership.user_id == user.id, Membership.team_id == team.id)
                .with_for_update()
            )
        )
        if existing is not None:
            if not existing.is_legacy_home:
                # Reappearance never auto-enables an administratively disabled row.
                if canonical is None:
                    existing.is_disabled = True
            return
        if canonical is not None:
            profile = await self.provider.user(subject)
            await TenantSignupService(self.db, self.provider).reconcile_invitations(
                subject, profile
            )
