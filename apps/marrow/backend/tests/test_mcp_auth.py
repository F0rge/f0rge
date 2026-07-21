from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp.auth import BearerTokenVerifier
from app.models.user_settings import UserSettings
from app.services.settings_service import SettingsService
from f0rge_db.tenant import apply_service_role


@pytest.fixture(autouse=True)
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "settings_encryption_key", key)
    import importlib
    import app.services.llm.encryption as enc_mod

    importlib.reload(enc_mod)
    import app.mcp.auth as auth_mod

    importlib.reload(auth_mod)
    return key


async def test_valid_token_passes_verification(async_db: AsyncSession) -> None:
    """A matching token returns an AccessToken bound to the owning user_id."""
    svc = SettingsService(async_db)
    resp = await svc.regenerate_external_token()

    result = await async_db.execute(
        select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
    )
    row = result.scalar_one()
    assert row.external_api_token_hash is not None
    expected_user_id = str(row.user_id)

    verifier = BearerTokenVerifier()
    with patch("app.mcp.auth.make_main_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        access_token = await verifier.verify_token(resp.token)

    assert access_token is not None
    assert access_token.client_id == expected_user_id
    assert access_token.token == resp.token


async def test_wrong_token_returns_none(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    await svc.regenerate_external_token()

    verifier = BearerTokenVerifier()
    wrong_token = secrets.token_urlsafe(32)

    with patch("app.mcp.auth.make_main_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        access_token = await verifier.verify_token(wrong_token)

    assert access_token is None


async def test_revoked_token_returns_none(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.regenerate_external_token()
    await svc.revoke_external_token()

    result = await async_db.execute(
        select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
    )
    row = result.scalar_one()
    assert row.external_api_token_hash is None

    verifier = BearerTokenVerifier()
    with patch("app.mcp.auth.make_main_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        access_token = await verifier.verify_token(resp.token)

    assert access_token is None


async def test_no_settings_row_returns_none() -> None:
    verifier = BearerTokenVerifier()

    with patch("app.mcp.auth.make_main_session") as mock_session_ctx:
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        mock_db.rollback = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        access_token = await verifier.verify_token("some-token")

    assert access_token is None


async def test_verify_survives_empty_app_user_id_guc(async_db: AsyncSession) -> None:
    """Contaminated pool GUC '' must not 500 — apply_service_role stamps nil UUID."""
    await async_db.execute(sa.text("SELECT set_config('app.user_id', '', false)"))
    await apply_service_role(async_db, "mcp_auth")
    uid = (await async_db.execute(sa.text("SELECT current_setting('app.user_id', true)"))).scalar()
    assert uid == "00000000-0000-0000-0000-000000000000"
    # RLS cast must not throw on the sentinel under mcp_auth.
    result = await async_db.execute(select(UserSettings).limit(1))
    result.scalars().first()  # may be None; must not raise


async def test_verify_uses_hash_lookup_not_decrypt(async_db: AsyncSession) -> None:
    """Verifier matches via external_api_token_hash, not ciphertext decryption."""
    svc = SettingsService(async_db)
    resp = await svc.regenerate_external_token()

    result = await async_db.execute(
        select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
    )
    row = result.scalar_one()
    assert row.external_api_token_hash is not None
    expected_user_id = str(row.user_id)
    row.external_api_token_encrypted = b"corrupt-ciphertext"
    await async_db.flush()

    verifier = BearerTokenVerifier()
    with patch("app.mcp.auth.make_main_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        access_token = await verifier.verify_token(resp.token)

    assert access_token is not None
    assert access_token.client_id == expected_user_id
