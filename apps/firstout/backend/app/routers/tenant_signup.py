from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.config import settings
from app.services.tenant_host import validate_slug

router = APIRouter(prefix="/api/v1/tenant-signup", tags=["tenant-signup"])


class SignupIntent(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str


@router.get("/status")
async def signup_status() -> dict:
    return {
        "enabled": settings.tenant_signup_enabled,
        "billing_disabled": settings.billing_disabled,
        "billing_test_mode": settings.billing_test_mode,
        "mode": "invite-only",
    }


@router.post("/preview")
async def signup_preview(body: SignupIntent) -> dict:
    if not settings.tenant_signup_enabled:
        raise HTTPException(503, "Tenant signup is invite-only during isolation rollout")
    if not settings.billing_disabled or not settings.billing_test_mode:
        raise HTTPException(503, "Live billing is not implemented")
    return {
        "name": body.name,
        "slug": validate_slug(body.slug),
        "billing": "disabled",
        "provisioned": False,
        "next_step": "Engineering-approved Clerk test provisioning",
    }
