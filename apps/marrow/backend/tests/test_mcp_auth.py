from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp.auth import BearerTokenVerifier
from app.models.user_settings import UserSettings
from app.services.settings_service import SettingsService


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

    verifier = BearerTokenVerifier()
    with patch("app.mcp.auth.make_main_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        access_token = await verifier.verify_token(resp.token)

    assert access_token is not None
    assert access_token.client_id == str(row.user_id)
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
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: []))
        )
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        access_token = await verifier.verify_token("some-token")

    assert access_token is None


async def test_corrupt_ciphertext_returns_none() -> None:
    """If decryption fails (bad ciphertext), verify_token should return None, not raise."""
    verifier = BearerTokenVerifier()

    mock_row = MagicMock()
    mock_row.external_api_token_encrypted = b"corrupt-data-that-cannot-decrypt"

    with patch("app.mcp.auth.make_main_session") as mock_session_ctx:
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [mock_row]))
        )
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        access_token = await verifier.verify_token("some-token")

    assert access_token is None
