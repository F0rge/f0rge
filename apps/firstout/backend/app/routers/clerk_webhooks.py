from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies.tenant_signup import get_clerk_webhook_service
from app.services.clerk_webhooks import ClerkWebhookService, verify_webhook  # noqa: F401

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/clerk")
async def clerk_webhook(
    request: Request, service: ClerkWebhookService = Depends(get_clerk_webhook_service)
) -> dict:
    return await service.receive(request)
