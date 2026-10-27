from __future__ import annotations

import asyncio
import datetime
import hashlib
import secrets
import time
from urllib.parse import quote

from fastapi import BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.password_reset_token import PasswordResetTokenCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import UserCRUD
from app.exceptions import RateLimitedError
from app.models.password_reset_token import PasswordResetToken
from app.schemas.auth import PasswordResetConfirmRequest, PasswordResetMessage
from app.services.auth import hash_password, validate_password
from app.services.comms.plain_email import deliver_plain_message, mailbox_or_none
from f0rge_core.exceptions import ValidationError
from f0rge_db.crud import unit_of_work

NEUTRAL_MESSAGE = "If an account exists for that email, we sent password reset instructions."
CONFIRM_MESSAGE = "Your password has been reset. You can log in with the new password."
INVALID_TOKEN = "This reset link is invalid."
EXPIRED_TOKEN = "This reset link has expired."
USED_TOKEN = "This reset link has already been used."
DISABLED_ACCOUNT = "This account is disabled."
PASSWORD_MISMATCH = "Passwords do not match."
RESET_EMAIL_SUBJECT = "Reset your Firstout password"

TOKEN_TTL = datetime.timedelta(hours=1)
NEUTRAL_MIN_SECONDS = 0.3

REQUEST_PER_EMAIL = 5
REQUEST_PER_IP = 20
REQUEST_WINDOW_SECONDS = 60 * 60
CONFIRM_PER_IP = 10
CONFIRM_WINDOW_SECONDS = 15 * 60


class SlidingWindowLimiter:
    """In-process limiter. Firstout has no shared rate-limit store; one API replica."""

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = {}

    def allow(self, key: str, *, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        recent = [stamp for stamp in self._events.get(key, []) if now - stamp < window_seconds]
        if len(recent) >= limit:
            self._events[key] = recent
            return False
        recent.append(now)
        self._events[key] = recent
        return True

    def reset(self) -> None:
        self._events.clear()


limiter = SlidingWindowLimiter()


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_app_base() -> str:
    explicit = settings.public_app_url.strip().rstrip("/")
    if explicit:
        return explicit
    if settings.cors_origins:
        return str(settings.cors_origins[0]).strip().rstrip("/")
    return "http://localhost:3003"


def reset_link(token: str) -> str:
    return f"{public_app_base()}/reset-password?token={quote(token, safe='')}"


def reset_email_body(link: str) -> str:
    return (
        "Someone asked to reset the password for your Firstout account.\n\n"
        "Open this link to choose a new password. "
        "The link expires in one hour and can only be used once.\n\n"
        f"{link}\n\n"
        "If you did not ask for this, you can ignore this email. "
        "Your password will stay the same.\n\n"
        "Firstout\n"
    )


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    if request.client is not None and request.client.host:
        return request.client.host[:64]
    return "unknown"


class PasswordResetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserCRUD(db)
        self.tokens = PasswordResetTokenCRUD(db)
        self.team_settings = TeamSettingsCRUD(db)

    async def request_reset(
        self,
        email: str,
        request: Request,
        background: BackgroundTasks,
    ) -> PasswordResetMessage:
        self._enforce_request_limits(email, request)
        started = time.monotonic()
        await self._issue(email, background)
        await self._pad(started)
        return PasswordResetMessage(message=NEUTRAL_MESSAGE)

    async def confirm_reset(
        self,
        body: PasswordResetConfirmRequest,
        request: Request,
    ) -> PasswordResetMessage:
        self._enforce_confirm_limit(request)
        if body.password != body.password_confirm:
            raise ValidationError(PASSWORD_MISMATCH)
        validate_password(body.password)

        token = await self.tokens.get_by_hash_for_update(hash_reset_token(body.token))
        if token is None:
            raise ValidationError(INVALID_TOKEN)
        if token.used_at is not None:
            raise ValidationError(USED_TOKEN)
        if token.expires_at <= datetime.datetime.utcnow():
            raise ValidationError(EXPIRED_TOKEN)

        user = await self.users.get_by_id(token.user_id)
        if user is None:
            raise ValidationError(INVALID_TOKEN)
        if user.is_disabled:
            async with unit_of_work(self.db):
                token.used_at = datetime.datetime.utcnow()
            raise ValidationError(DISABLED_ACCOUNT)

        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            await self.tokens.invalidate_unused(user.id, now)
            token.used_at = now
            user.password_hash = hash_password(body.password)
            user.token_version = int(user.token_version) + 1
        return PasswordResetMessage(message=CONFIRM_MESSAGE)

    def _enforce_request_limits(self, email: str, request: Request) -> None:
        email_key = email.strip().lower()
        ip = client_ip(request)
        if not limiter.allow(
            f"reset-request-email:{email_key}",
            limit=REQUEST_PER_EMAIL,
            window_seconds=REQUEST_WINDOW_SECONDS,
        ):
            raise RateLimitedError()
        if not limiter.allow(
            f"reset-request-ip:{ip}",
            limit=REQUEST_PER_IP,
            window_seconds=REQUEST_WINDOW_SECONDS,
        ):
            raise RateLimitedError()

    def _enforce_confirm_limit(self, request: Request) -> None:
        ip = client_ip(request)
        if not limiter.allow(
            f"reset-confirm-ip:{ip}",
            limit=CONFIRM_PER_IP,
            window_seconds=CONFIRM_WINDOW_SECONDS,
        ):
            raise RateLimitedError()

    async def _issue(self, email: str, background: BackgroundTasks) -> None:
        user = await self.users.get_by_email(email)
        if user is None or user.is_disabled:
            return
        team_settings = await self.team_settings.get_or_create_for_team(user.team_id)
        config = mailbox_or_none(team_settings)
        if config is None:
            return

        raw = secrets.token_urlsafe(32)
        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            await self.tokens.invalidate_unused(user.id, now)
            await self.tokens.add_and_flush(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=hash_reset_token(raw),
                    expires_at=now + TOKEN_TTL,
                )
            )
        link = reset_link(raw)
        background.add_task(
            deliver_plain_message,
            config,
            to=user.email,
            subject=RESET_EMAIL_SUBJECT,
            body_text=reset_email_body(link),
        )

    async def _pad(self, started: float) -> None:
        remaining = NEUTRAL_MIN_SECONDS - (time.monotonic() - started)
        if remaining > 0:
            await asyncio.sleep(remaining)
