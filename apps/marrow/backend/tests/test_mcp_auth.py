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
from app.models.external_api_token import ExternalApiToken
from app.models.user_settings import UserSettings
from app.services.llm.encryption import hash_external_api_token
from app.services.settings_service import SettingsService
from f0rge_db.tenant import apply_service_role
from tests.test_external_token import _seed_legacy_hash


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


def _verifier_session(async_db: AsyncSession):
    return patch("app.mcp.auth.make_main_session")


async def _verify(async_db: AsyncSession, token: str):
    verifier = BearerTokenVerifier()
    with _verifier_session(async_db) as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        return await verifier.verify_token(token)


async def test_valid_token_passes_verification(async_db: AsyncSession) -> None:
    """A matching token returns an AccessToken bound to the owning user_id."""
    svc = SettingsService(async_db)
    resp = await svc.create_external_token("phone")

    token_row = (
        await async_db.execute(select(ExternalApiToken).where(ExternalApiToken.id == resp.id))
    ).scalar_one()
    assert token_row.token_hash == hash_external_api_token(resp.token)
    expected_user_id = str(token_row.user_id)

    access_token = await _verify(async_db, resp.token)

    assert access_token is not None
    assert access_token.client_id == expected_user_id
    assert access_token.token == resp.token


async def test_wrong_token_returns_none(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    await svc.create_external_token("phone")

    access_token = await _verify(async_db, secrets.token_urlsafe(32))

    assert access_token is None


async def test_revoked_token_returns_none(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.create_external_token("phone")
    await svc.revoke_external_token(resp.id)

    remaining = (
        await async_db.execute(select(ExternalApiToken).where(ExternalApiToken.id == resp.id))
    ).scalar_one_or_none()
    assert remaining is None

    access_token = await _verify(async_db, resp.token)

    assert access_token is None


async def test_legacy_hash_and_second_token_both_authenticate(async_db: AsyncSession) -> None:
    """Copied hash keeps working; a new token is additive; revoking one leaves the other."""
    legacy_plaintext = "legacy-token-still-valid-0123456789abcd"
    original_hash = await _seed_legacy_hash(async_db, legacy_plaintext)
    svc = SettingsService(async_db)
    second = await svc.create_external_token("phone")

    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    assert settings_row.external_api_token_hash == original_hash
    expected_user_id = str(settings_row.user_id)

    legacy_access = await _verify(async_db, legacy_plaintext)
    second_access = await _verify(async_db, second.token)
    assert legacy_access is not None
    assert second_access is not None
    assert legacy_access.client_id == expected_user_id
    assert second_access.client_id == legacy_access.client_id

    await svc.revoke_external_token(second.id)

    assert await _verify(async_db, legacy_plaintext) is not None
    assert await _verify(async_db, second.token) is None

    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    assert settings_row.external_api_token_hash == original_hash


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
    """Verifier matches the token-table hash, not ciphertext decryption."""
    svc = SettingsService(async_db)
    resp = await svc.create_external_token("phone")

    result = await async_db.execute(
        select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
    )
    row = result.scalar_one()
    expected_user_id = str(row.user_id)
    row.external_api_token_encrypted = b"corrupt-ciphertext"
    await async_db.flush()

    access_token = await _verify(async_db, resp.token)

    assert access_token is not None
    assert access_token.client_id == expected_user_id


def _route_paths(app) -> list[str]:
    return [getattr(route, "path", "") or "" for route in app.routes]


def test_http_app_does_not_advertise_oauth_discovery() -> None:
    """Cursor ignores mcp.json Bearer headers if RFC 9728 metadata returns 200."""
    from starlette.testclient import TestClient

    from app.mcp.server import create_server

    app = create_server().streamable_http_app()
    assert not any("oauth-protected-resource" in path for path in _route_paths(app))
    assert not any("oauth-authorization-server" in path for path in _route_paths(app))

    client = TestClient(app)
    metadata = client.get("/.well-known/oauth-protected-resource")
    assert metadata.status_code == 404
    as_meta = client.get("/.well-known/oauth-authorization-server")
    assert as_meta.status_code == 404

    unauth = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert unauth.status_code == 401
    www = unauth.headers.get("www-authenticate", "")
    assert "resource_metadata" not in www
