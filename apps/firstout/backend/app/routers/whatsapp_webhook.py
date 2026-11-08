from __future__ import annotations

from typing import Optional
import json

from sqlalchemy import select
from app.database import tenant_session
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.exceptions import ForbiddenError

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import PlainTextResponse

from app.dependencies.auth import get_whatsapp_webhook_service
from app.services.comms.whatsapp import WhatsAppWebhookService

whatsapp_webhook_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@whatsapp_webhook_router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
    service: WhatsAppWebhookService = Depends(get_whatsapp_webhook_service),
) -> PlainTextResponse:
    return PlainTextResponse(service.verify_challenge(hub_mode, hub_verify_token, hub_challenge))


@whatsapp_webhook_router.post("/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    service: WhatsAppWebhookService = Depends(get_whatsapp_webhook_service),
    x_hub_signature_256: Optional[str] = Header(default=None),
) -> dict:
    raw = await request.body()
    try:
        payload = json.loads(raw)
        phone_ids = {
            change["value"]["metadata"]["phone_number_id"]
            for entry in payload.get("entry", [])
            for change in entry.get("changes", [])
        }
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ForbiddenError("Invalid WhatsApp tenant routing") from exc
    if len(phone_ids) != 1 or not x_hub_signature_256:
        raise ForbiddenError("Invalid WhatsApp tenant routing")
    phone_id = next(iter(phone_ids))
    async with tenant_session() as directory:
        ids = list(await directory.scalars(select(Team.id).where(Team.status == "active")))
    matches = []
    for team_id in ids:
        async with tenant_session(team_id) as db:
            row = await db.scalar(
                select(TeamSettings).where(TeamSettings.wa_phone_number_id == phone_id)
            )
            if row is not None and row.wa_app_secret_encrypted:
                matches.append(team_id)
    if len(matches) != 1:
        raise ForbiddenError("Unknown WhatsApp tenant")
    async with tenant_session(matches[0]) as db:
        await WhatsAppWebhookService(db).handle_post(raw, x_hub_signature_256)
    return {"ok": True}
