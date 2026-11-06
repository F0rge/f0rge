from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError
from app.config import settings
from app.database import get_db
from app.models.clerk_webhook_event import ClerkWebhookEvent

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


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


@router.post("/clerk")
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    payload = await request.body()
    if len(payload) > 1_000_000:
        raise HTTPException(413, "Webhook too large")
    event = verify_webhook(payload, dict(request.headers))
    event_id = request.headers["svix-id"]
    result = await db.execute(
        insert(ClerkWebhookEvent)
        .values(svix_id=event_id, event_type=event["type"])
        .on_conflict_do_nothing()
        .returning(ClerkWebhookEvent.svix_id)
    )
    if result.scalar_one_or_none() is None:
        return {"status": "duplicate"}
    # Dual-auth quarantine: no webhook may create/link identities by email, grant
    # roles, revoke local home access, or delete staff. Explicit import/provisioning
    # owns links. Receipt is retained so operators can reconcile signed events.
    await db.commit()
    return {"status": "quarantined"}
