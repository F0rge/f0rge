from __future__ import annotations

import hashlib
import importlib.util
import uuid
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_api_token import LEGACY_EXTERNAL_API_TOKEN_NAME, ExternalApiToken
from app.models.user_settings import UserSettings
from app.schemas.settings import ExternalTokenCreate, ExternalTokenResponse, SettingsResponse
from app.services.llm.encryption import encrypt, hash_external_api_token
from app.services.settings_service import SettingsService
from f0rge_core.exceptions import NotFoundError

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions" / "057_external_api_tokens.py"
)


@pytest.fixture(autouse=True)
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "settings_encryption_key", key)
    import importlib
    import app.services.llm.encryption as enc_mod

    importlib.reload(enc_mod)
    return key


def _copy_legacy_hashes(connection) -> None:
    spec = importlib.util.spec_from_file_location(
        "migration_057_external_api_tokens", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.copy_existing_external_api_token_hashes(connection)


async def _seed_legacy_hash(async_db: AsyncSession, plaintext: str) -> str:
    """Store a pre-migration hash on user_settings, then copy it. Never replace it."""
    svc = SettingsService(async_db)
    row = await svc._get_or_create_row()
    token_hash = hash_external_api_token(plaintext)
    row.external_api_token_hash = token_hash
    row.external_api_token_encrypted = encrypt(plaintext)
    await svc.crud.commit_refresh(row)
    connection = await async_db.connection()
    await connection.run_sync(_copy_legacy_hashes)
    return token_hash


async def test_create_returns_43_char_urlsafe_token(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.create_external_token("phone")
    assert isinstance(resp, ExternalTokenResponse)
    # secrets.token_urlsafe(32) always produces 43 URL-safe chars.
    assert len(resp.token) == 43
    assert all(
        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in resp.token
    )

    result = await async_db.execute(select(ExternalApiToken).where(ExternalApiToken.id == resp.id))
    token_row = result.scalar_one()
    assert token_row.token_hash == hash_external_api_token(resp.token)
    assert token_row.token_hash == hashlib.sha256(resp.token.encode()).hexdigest()
    assert token_row.created_at is not None
    assert token_row.name == "phone"
    assert resp.name == "phone"

    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    # A newly issued token must not occupy the legacy single-hash column.
    assert settings_row.external_api_token_hash is None
    assert settings_row.external_api_token_encrypted is None


async def test_second_create_keeps_the_first_token(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    first = await svc.create_external_token("phone")
    second = await svc.create_external_token("laptop")
    assert first.token != second.token
    assert first.name == "phone"
    assert second.name == "laptop"

    rows = (
        (
            await async_db.execute(
                select(ExternalApiToken).where(
                    ExternalApiToken.user_id == settings.default_storage_user_id
                )
            )
        )
        .scalars()
        .all()
    )
    hashes = {row.token_hash for row in rows}
    assert hash_external_api_token(first.token) in hashes
    assert hash_external_api_token(second.token) in hashes


async def test_legacy_hash_is_copied_and_not_overwritten(async_db: AsyncSession) -> None:
    """The hash already on user_settings is copied, then left exactly as it was."""
    legacy_plaintext = "legacy-token-still-valid-0123456789abcd"
    original_hash = await _seed_legacy_hash(async_db, legacy_plaintext)

    copied = (
        await async_db.execute(
            select(ExternalApiToken).where(ExternalApiToken.token_hash == original_hash)
        )
    ).scalar_one()
    assert copied.name == LEGACY_EXTERNAL_API_TOKEN_NAME
    assert copied.created_at is None

    svc = SettingsService(async_db)
    created = await svc.create_external_token("laptop")
    assert created.token != legacy_plaintext
    assert created.name == "laptop"

    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    assert settings_row.external_api_token_hash == original_hash

    listed = await svc.list_external_tokens()
    assert {item.id for item in listed.tokens} == {copied.id, created.id}
    legacy_item = next(item for item in listed.tokens if item.id == copied.id)
    assert legacy_item.name == "existing token"
    assert legacy_item.created_at is None
    fresh_item = next(item for item in listed.tokens if item.id == created.id)
    assert fresh_item.created_at is not None
    assert fresh_item.name == "laptop"


async def test_revoke_one_token_leaves_the_other(async_db: AsyncSession) -> None:
    legacy_plaintext = "legacy-token-still-valid-0123456789abcd"
    original_hash = await _seed_legacy_hash(async_db, legacy_plaintext)
    svc = SettingsService(async_db)
    created = await svc.create_external_token("phone")

    await svc.revoke_external_token(created.id)

    remaining = (await svc.list_external_tokens()).tokens
    assert len(remaining) == 1
    assert remaining[0].name == "existing token"
    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    assert settings_row.external_api_token_hash == original_hash

    await svc.revoke_external_token(remaining[0].id)
    assert (await svc.list_external_tokens()).tokens == []
    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    # Revoking the copied token clears the snapshot. It does not replace the hash.
    assert settings_row.external_api_token_hash is None
    assert settings_row.external_api_token_encrypted is None


async def test_revoking_new_token_does_not_clear_a_different_legacy_hash(
    async_db: AsyncSession,
) -> None:
    original_hash = await _seed_legacy_hash(async_db, "legacy-token-still-valid-0123456789abcd")
    svc = SettingsService(async_db)
    created = await svc.create_external_token("phone")
    await svc.revoke_external_token(created.id)
    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    assert settings_row.external_api_token_hash == original_hash


async def test_settings_response_shows_token_present_after_create(
    async_db: AsyncSession,
) -> None:
    svc = SettingsService(async_db)
    await svc.create_external_token("phone")
    resp = await svc.get()
    assert resp.has_external_api_token is True


async def test_revoke_last_token_clears_presence(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    created = await svc.create_external_token("phone")
    await svc.revoke_external_token(created.id)
    revoked = await svc.get()
    assert isinstance(revoked, SettingsResponse)
    assert revoked.has_external_api_token is False


async def test_revoke_unknown_token_raises(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    with pytest.raises(NotFoundError):
        await svc.revoke_external_token(uuid.uuid4())
    assert (await svc.get()).has_external_api_token is False


async def test_plaintext_not_stored_in_db(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.create_external_token("phone")

    token_row = (
        await async_db.execute(select(ExternalApiToken).where(ExternalApiToken.id == resp.id))
    ).scalar_one()
    assert resp.token.encode() not in token_row.token_hash.encode()
    assert resp.token not in token_row.name


async def test_has_external_api_token_false_when_only_legacy_ciphertext(
    async_db: AsyncSession,
) -> None:
    """Ciphertext without a copied hash must not report an active token."""
    svc = SettingsService(async_db)
    row = await svc._get_or_create_row()
    row.external_api_token_encrypted = encrypt("orphan-token-without-hash")
    row.external_api_token_hash = None
    await svc.crud.commit_refresh(row)

    resp = await svc.get()
    assert resp.has_external_api_token is False


async def test_copy_is_idempotent(async_db: AsyncSession) -> None:
    plaintext = "legacy-token-still-valid-0123456789abcd"
    original_hash = await _seed_legacy_hash(async_db, plaintext)
    connection = await async_db.connection()
    await connection.run_sync(_copy_legacy_hashes)
    rows = (
        (
            await async_db.execute(
                select(ExternalApiToken).where(ExternalApiToken.token_hash == original_hash)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].name == "existing token"
    settings_row = (
        await async_db.execute(
            select(UserSettings).where(UserSettings.user_id == settings.default_storage_user_id)
        )
    ).scalar_one()
    assert settings_row.external_api_token_hash == original_hash


def test_token_name_is_required_and_trimmed() -> None:
    from pydantic import ValidationError

    assert ExternalTokenCreate(name="  cursor  ").name == "cursor"
    with pytest.raises(ValidationError):
        ExternalTokenCreate(name="   ")
    with pytest.raises(ValidationError):
        ExternalTokenCreate(name="x" * 65)
