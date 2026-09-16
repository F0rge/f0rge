from __future__ import annotations

from typing import Optional

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
    await service.handle_post(await request.body(), x_hub_signature_256)
    return {"ok": True}


@whatsapp_webhook_router.get("/whatsapp/{slug}")
async def verify_whatsapp_webhook_for_tenant(
    slug: str,
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
    service: WhatsAppWebhookService = Depends(get_whatsapp_webhook_service),
) -> PlainTextResponse:
    return PlainTextResponse(service.verify_challenge(hub_mode, hub_verify_token, hub_challenge))


@whatsapp_webhook_router.post("/whatsapp/{slug}")
async def receive_whatsapp_webhook_for_tenant(
    slug: str,
    request: Request,
    service: WhatsAppWebhookService = Depends(get_whatsapp_webhook_service),
    x_hub_signature_256: Optional[str] = Header(default=None),
) -> dict:
    await service.handle_post(await request.body(), x_hub_signature_256)
    return {"ok": True}
