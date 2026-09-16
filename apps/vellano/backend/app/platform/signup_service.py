from __future__ import annotations

import datetime
import hashlib
import logging
import secrets
import uuid
from typing import Optional

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.platform.crud import SignupCRUD, TenantCRUD
from app.platform.mailer import send_verify_email
from app.platform.models import (
    SIGNUP_STATUS_EXPIRED,
    SIGNUP_STATUS_FAILED,
    SIGNUP_STATUS_PENDING_VERIFY,
    SIGNUP_STATUS_PROVISIONING,
    SIGNUP_STATUS_READY,
    SIGNUP_STATUS_VERIFIED,
    Signup,
)
from app.platform.service import (
    slug_availability_reason,
    validate_slug,
    workspace_origin,
)
from app.schemas.platform_signup import (
    SignupCreateRequest,
    SignupCreateResponse,
    SignupStatusResponse,
    SignupVerifyResponse,
    SlugAvailabilityResponse,
)
from app.services.auth import hash_password
from f0rge_core.exceptions import ConflictError, ValidationError
from f0rge_db.crud import unit_of_work

logger = logging.getLogger(__name__)

VERIFY_TTL = datetime.timedelta(hours=24)
RESEND_COOLDOWN = datetime.timedelta(seconds=60)
MAX_RESENDS = 3
MAX_ACTIVE_PER_EMAIL = 3
MAX_SIGNUPS_PER_IP_HOUR = 10


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SignupService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SignupCRUD(db)
        self.tenants = TenantCRUD(db)

    async def slug_availability(self, slug: str) -> SlugAvailabilityResponse:
        reason = slug_availability_reason(slug)
        if reason is not None:
            return SlugAvailabilityResponse(available=False, reason=reason)
        value = validate_slug(slug)
        if await self.tenants.get_by_slug(value) is not None:
            return SlugAvailabilityResponse(available=False, reason="taken")
        if await self.crud.get_inflight_by_slug(value) is not None:
            return SlugAvailabilityResponse(available=False, reason="taken")
        return SlugAvailabilityResponse(available=True)

    async def create(
        self,
        data: SignupCreateRequest,
        *,
        ip: Optional[str],
        user_agent: Optional[str],
        background: BackgroundTasks,
    ) -> SignupCreateResponse:
        if ip:
            since = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
            if await self.crud.count_created_by_ip_since(ip, since) >= MAX_SIGNUPS_PER_IP_HOUR:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many signup attempts",
                )
        email = str(data.email).strip().lower()
        if await self.crud.count_active_by_email(email) >= MAX_ACTIVE_PER_EMAIL:
            return SignupCreateResponse(
                signup_id=uuid.uuid4(),
                status=SIGNUP_STATUS_PENDING_VERIFY,
            )
        availability = await self.slug_availability(data.slug)
        if not availability.available:
            if availability.reason == "taken":
                raise ConflictError("taken")
            raise ValidationError(availability.reason or "Invalid slug")

        token = secrets.token_urlsafe(32)
        signup = Signup(
            email=email,
            legal_name=data.legal_name.strip(),
            trading_name=(data.trading_name or "").strip() or None,
            slug=validate_slug(data.slug),
            owner_name=data.owner_name.strip(),
            password_hash=hash_password(data.password),
            status=SIGNUP_STATUS_PENDING_VERIFY,
            verify_token_hash=_hash_token(token),
            verify_expires_at=datetime.datetime.utcnow() + VERIFY_TTL,
            privacy_version=data.privacy_version,
            authorised_confirmed_at=datetime.datetime.utcnow(),
            created_ip=ip,
            user_agent=user_agent,
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(signup)
        except IntegrityError:
            raise ConflictError("taken") from None
        background.add_task(send_verify_email, to=email, token=token)
        return SignupCreateResponse(signup_id=signup.id, status=signup.status)

    async def resend(self, signup_id: uuid.UUID, background: BackgroundTasks) -> None:
        signup = await self._get(signup_id)
        signup = await self._expire_if_stale(signup)
        if signup.status != SIGNUP_STATUS_PENDING_VERIFY:
            raise ValidationError("Signup cannot be resent")
        if signup.attempts >= MAX_RESENDS:
            raise ValidationError("Resend limit reached")
        if signup.updated_at and datetime.datetime.utcnow() - signup.updated_at < RESEND_COOLDOWN:
            raise ValidationError("Wait before resending")
        token = secrets.token_urlsafe(32)
        signup.verify_token_hash = _hash_token(token)
        signup.verify_expires_at = datetime.datetime.utcnow() + VERIFY_TTL
        signup.attempts = int(signup.attempts or 0) + 1
        await self.db.commit()
        background.add_task(send_verify_email, to=signup.email, token=token)

    async def verify(
        self,
        token: str,
        background: BackgroundTasks,
    ) -> SignupVerifyResponse:
        signup = await self.crud.get_by_verify_token_hash(_hash_token(token))
        if signup is None:
            raise ValidationError("That link is not valid")
        signup = await self._expire_if_stale(signup)
        if signup.status != SIGNUP_STATUS_PENDING_VERIFY:
            raise ValidationError("That link is not valid")
        if signup.verify_expires_at and signup.verify_expires_at < datetime.datetime.utcnow():
            signup.status = SIGNUP_STATUS_EXPIRED
            signup.verify_token_hash = None
            await self.db.commit()
            raise ValidationError("That link is not valid")
        signup.status = SIGNUP_STATUS_VERIFIED
        signup.verified_at = datetime.datetime.utcnow()
        signup.verify_token_hash = None
        await self.db.commit()
        if settings.platform_signup_mode == "instant":
            background.add_task(self._provision_later, signup.id)
            return SignupVerifyResponse(signup_id=signup.id, status=SIGNUP_STATUS_PROVISIONING)
        return SignupVerifyResponse(signup_id=signup.id, status=signup.status)

    async def status(self, signup_id: uuid.UUID) -> SignupStatusResponse:
        signup = await self._get(signup_id)
        signup = await self._expire_if_stale(signup)
        workspace_url = None
        failure = None
        if signup.status == SIGNUP_STATUS_READY:
            workspace_url = workspace_origin(signup.slug)
        if signup.status == SIGNUP_STATUS_FAILED:
            failure = "We could not finish creating your workspace. Try again later."
        return SignupStatusResponse(
            status=signup.status,
            workspace_url=workspace_url,
            failure=failure,
        )

    async def _get(self, signup_id: uuid.UUID) -> Signup:
        signup = await self.crud.get_by_id(signup_id)
        if signup is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return signup

    async def _expire_if_stale(self, signup: Signup) -> Signup:
        if (
            signup.status == SIGNUP_STATUS_PENDING_VERIFY
            and signup.verify_expires_at
            and signup.verify_expires_at < datetime.datetime.utcnow()
        ):
            signup.status = SIGNUP_STATUS_EXPIRED
            signup.verify_token_hash = None
            await self.db.commit()
        return signup

    @staticmethod
    async def _provision_later(signup_id: uuid.UUID) -> None:
        from app.platform.database import platform_sessionmaker
        from app.platform.provisioning import ProvisioningService

        try:
            await ProvisioningService().provision(signup_id)
        except Exception:
            logger.exception("background provision failed")
            maker = platform_sessionmaker()
            async with maker() as db:
                signup = await SignupCRUD(db).get_by_id(signup_id)
                if signup is not None and signup.status not in (
                    SIGNUP_STATUS_READY,
                    SIGNUP_STATUS_FAILED,
                ):
                    signup.status = SIGNUP_STATUS_FAILED
                    signup.failure_reason = "provision_failed"
                    await db.commit()
