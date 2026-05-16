from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.settings import ExternalTokenResponse, SettingsResponse
from app.services.settings_service import SettingsService


@pytest.fixture(autouse=True)
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "settings_encryption_key", key)
    import importlib
    import app.services.llm.encryption as enc_mod

    importlib.reload(enc_mod)
    return key


async def test_regenerate_returns_43_char_urlsafe_token(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.regenerate_external_token()
    assert isinstance(resp, ExternalTokenResponse)
    # secrets.token_urlsafe(32) always produces 43 URL-safe chars.
    assert len(resp.token) == 43
    assert all(
        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        for c in resp.token
    )


async def test_regenerate_second_call_produces_different_token(
    async_db: AsyncSession,
) -> None:
    svc = SettingsService(async_db)
    r1 = await svc.regenerate_external_token()
    r2 = await svc.regenerate_external_token()
    # Each call generates a fresh token and a new ciphertext.
    assert r1.token != r2.token


async def test_regenerate_invalidates_previous_token(async_db: AsyncSession) -> None:
    """After regeneration, only the newest token should decrypt correctly."""
    from app.models.user_settings import UserSettings
    from sqlalchemy import select
    from app.services.llm.encryption import decrypt

    svc = SettingsService(async_db)
    r1 = await svc.regenerate_external_token()
    r2 = await svc.regenerate_external_token()

    # Read the stored ciphertext.
    result = await async_db.execute(select(UserSettings).where(UserSettings.id == 1))
    row = result.scalar_one()
    stored_plaintext = decrypt(row.external_api_token_encrypted)

    # Only the second token matches what's stored.
    assert stored_plaintext == r2.token
    assert stored_plaintext != r1.token


async def test_settings_response_shows_token_present_after_regenerate(
    async_db: AsyncSession,
) -> None:
    svc = SettingsService(async_db)
    await svc.regenerate_external_token()
    resp = await svc.get()
    assert resp.has_external_api_token is True


async def test_revoke_clears_token_column(async_db: AsyncSession) -> None:
    from app.models.user_settings import UserSettings
    from sqlalchemy import select

    svc = SettingsService(async_db)
    await svc.regenerate_external_token()
    revoked = await svc.revoke_external_token()

    assert isinstance(revoked, SettingsResponse)
    assert revoked.has_external_api_token is False

    result = await async_db.execute(select(UserSettings).where(UserSettings.id == 1))
    row = result.scalar_one()
    assert row.external_api_token_encrypted is None


async def test_revoke_without_prior_token_is_safe(async_db: AsyncSession) -> None:
    """Calling revoke when no token exists should not raise."""
    svc = SettingsService(async_db)
    resp = await svc.revoke_external_token()
    assert resp.has_external_api_token is False


async def test_plaintext_not_stored_in_db(async_db: AsyncSession) -> None:
    from app.models.user_settings import UserSettings
    from sqlalchemy import select

    svc = SettingsService(async_db)
    resp = await svc.regenerate_external_token()

    result = await async_db.execute(select(UserSettings).where(UserSettings.id == 1))
    row = result.scalar_one()

    # The ciphertext bytes must not equal the plaintext token bytes.
    assert row.external_api_token_encrypted is not None
    assert resp.token.encode() not in row.external_api_token_encrypted
