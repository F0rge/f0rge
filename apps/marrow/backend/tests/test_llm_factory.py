from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_core.exceptions import ConflictError
from app.models.user_settings import UserSettings
from app.services.llm.factory import get_embedding_client, get_llm_client
from app.services.llm.openrouter import OpenRouterClient, OpenRouterEmbeddingClient


@pytest.fixture(autouse=True)
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "settings_encryption_key", key)
    import importlib
    import app.services.llm.encryption as enc_mod

    importlib.reload(enc_mod)
    return key


@pytest.fixture(autouse=True)
def clear_openrouter_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure env-var key is empty by default so tests control the source."""
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "")


async def test_get_llm_client_from_env(
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factory falls back to env var when no DB row exists."""
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "env-key-123")

    client = await get_llm_client(async_db)
    assert isinstance(client, OpenRouterClient)
    assert client._api_key == "env-key-123"


async def test_get_llm_client_from_db(
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factory uses DB-stored encrypted key over env var."""
    from app.services.llm.encryption import encrypt

    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "env-key-fallback")

    row = UserSettings(
        id=1,
        llm_api_key_encrypted=encrypt("db-stored-key"),
    )
    async_db.add(row)
    await async_db.flush()

    client = await get_llm_client(async_db)
    assert isinstance(client, OpenRouterClient)
    assert client._api_key == "db-stored-key"


async def test_get_llm_client_raises_when_no_key(async_db: AsyncSession) -> None:
    """Factory raises ConflictError when neither env nor DB has a key."""
    # env var already cleared by autouse fixture

    with pytest.raises(ConflictError, match="LLM not configured"):
        await get_llm_client(async_db)


async def test_get_embedding_client_from_env(
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "env-embed-key")

    client = await get_embedding_client(async_db)
    assert isinstance(client, OpenRouterEmbeddingClient)
    assert client._api_key == "env-embed-key"


async def test_get_embedding_client_raises_when_no_key(async_db: AsyncSession) -> None:
    with pytest.raises(ConflictError, match="Embedding client not configured"):
        await get_embedding_client(async_db)
