from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.settings import EmbeddingSettingsUpdate, LLMSettingsUpdate
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


async def test_get_returns_defaults_when_no_row(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.get()
    assert resp.llm_provider == "openrouter"
    assert resp.has_llm_api_key is False
    assert resp.has_embedding_api_key is False
    assert resp.has_external_api_token is False


async def test_update_llm_stores_key_encrypted(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.update_llm(LLMSettingsUpdate(llm_api_key="my-secret-key"))
    assert resp.has_llm_api_key is True
    # Plaintext must not appear in response fields.
    assert not hasattr(resp, "llm_api_key")
    assert not hasattr(resp, "llm_api_key_encrypted")


async def test_update_llm_does_not_echo_plaintext(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    data = LLMSettingsUpdate(llm_api_key="sensitive-plaintext")
    resp = await svc.update_llm(data)
    resp_dict = resp.model_dump()
    for value in resp_dict.values():
        assert "sensitive-plaintext" not in str(value)


async def test_update_llm_model(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.update_llm(
        LLMSettingsUpdate(llm_model="anthropic/claude-haiku-4-5")
    )
    assert resp.llm_model == "anthropic/claude-haiku-4-5"


async def test_update_embedding_stores_key_encrypted(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    resp = await svc.update_embedding(
        EmbeddingSettingsUpdate(embedding_api_key="embed-secret")
    )
    assert resp.has_embedding_api_key is True


async def test_get_after_update_reflects_changes(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    await svc.update_llm(LLMSettingsUpdate(llm_api_key="k", llm_model="m/model"))
    resp = await svc.get()
    assert resp.has_llm_api_key is True
    assert resp.llm_model == "m/model"


async def test_update_is_idempotent_upsert(async_db: AsyncSession) -> None:
    """Calling update_llm twice should not create two rows."""
    svc = SettingsService(async_db)
    await svc.update_llm(LLMSettingsUpdate(llm_api_key="first"))
    resp = await svc.update_llm(LLMSettingsUpdate(llm_api_key="second"))
    assert resp.has_llm_api_key is True
    # Only one singleton row should exist.
    from sqlalchemy import func, select
    from app.models.user_settings import UserSettings

    count = (
        await async_db.execute(select(func.count()).select_from(UserSettings))
    ).scalar_one()
    assert count == 1
