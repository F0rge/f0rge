"""Retired local reset capabilities cannot alter credentials or send mail."""

from __future__ import annotations

import datetime
import smtplib

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.password_reset import hash_reset_token
from tests.conftest import OWNER_EMAIL
from tests.test_comms_smtp import _FakeSMTP


@pytest.mark.parametrize("known_email", [False, True])
async def test_retired_reset_request_never_issues_mail_or_tokens(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    known_email: bool,
) -> None:
    _FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    before = (user.password_hash, user.token_version)
    tokens_before = list((await async_db.scalars(select(PasswordResetToken))).all())
    response = await owner_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": OWNER_EMAIL if known_email else "unknown@example.com"},
    )
    assert response.status_code == 400 and "Clerk" in response.json()["detail"]
    await async_db.refresh(user)
    assert (user.password_hash, user.token_version) == before
    assert list((await async_db.scalars(select(PasswordResetToken))).all()) == tokens_before
    assert _FakeSMTP.instances == []


@pytest.mark.parametrize("valid_token", [False, True])
async def test_retired_reset_cannot_consume_old_capability_or_replace_password(
    owner_client: AsyncClient, async_db: AsyncSession, valid_token: bool
) -> None:
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    raw_token = "owned-retained-local-reset-capability"
    stored = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    )
    async_db.add(stored)
    await async_db.flush()
    before = (user.password_hash, user.token_version)
    response = await owner_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token if valid_token else "invalid-local-capability",
            "password": "must-not-replace-password",
            "password_confirm": "must-not-replace-password",
        },
    )
    assert response.status_code == 400 and "Clerk" in response.json()["detail"]
    await async_db.refresh(user)
    await async_db.refresh(stored)
    assert (user.password_hash, user.token_version) == before
    assert stored.used_at is None
