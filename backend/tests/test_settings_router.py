from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from app.exceptions import ExternalServiceError
from app.services.llm.base import EmbeddingClient, LLMClient
from app.services.llm.factory import get_embedding_client, get_llm_client


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
def auth_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass auth middleware for settings router tests."""
    from app.middleware.auth import get_current_session
    from app.models.session import AuthSession
    from app.main import app

    fake_session = MagicMock(spec=AuthSession)

    async def _fake_session() -> AuthSession:
        return fake_session

    app.dependency_overrides[get_current_session] = _fake_session
    yield
    app.dependency_overrides.pop(get_current_session, None)


async def test_get_settings_initial_shape(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_api_key"] is False
    assert body["has_external_api_token"] is False
    assert "llm_provider" in body
    assert "embedding_provider" in body


async def test_put_llm_returns_has_key_true(async_client: AsyncClient) -> None:
    resp = await async_client.put(
        "/api/v1/settings/llm",
        json={"llm_api_key": "sk-test-key"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_api_key"] is True


async def test_put_llm_does_not_echo_plaintext(async_client: AsyncClient) -> None:
    await async_client.put(
        "/api/v1/settings/llm",
        json={"llm_api_key": "sk-secret-never-returned"},
    )
    resp = await async_client.get("/api/v1/settings")
    body_str = resp.text
    assert "sk-secret-never-returned" not in body_str
    assert "encrypted" not in body_str


async def test_put_does_not_include_encrypted_field(async_client: AsyncClient) -> None:
    resp = await async_client.put(
        "/api/v1/settings/llm",
        json={"llm_api_key": "any-key"},
    )
    assert "encrypted" not in resp.json()
    assert "llm_api_key_encrypted" not in resp.json()


async def test_llm_test_ok(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """test endpoint returns ok=true when client succeeds."""
    from app.main import app

    async def _mock_llm() -> LLMClient:
        mock = AsyncMock(spec=LLMClient)
        mock.complete.return_value = "hi"
        return mock

    app.dependency_overrides[get_llm_client] = _mock_llm
    try:
        resp = await async_client.post("/api/v1/settings/llm/test")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


async def test_llm_test_fail(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """test endpoint returns ok=false when client raises ExternalServiceError."""
    from app.main import app

    async def _mock_llm_fail() -> LLMClient:
        mock = AsyncMock(spec=LLMClient)
        mock.complete.side_effect = ExternalServiceError("upstream down")
        return mock

    app.dependency_overrides[get_llm_client] = _mock_llm_fail
    try:
        resp = await async_client.post("/api/v1/settings/llm/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert "upstream down" in body["detail"]
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


async def test_put_embedding_ignores_stray_key_field(async_client: AsyncClient) -> None:
    """embedding_api_key is not a field on EmbeddingSettingsUpdate anymore. Pydantic v2
    default (extra="ignore") drops unknown fields silently — no 422, key untouched."""
    resp = await async_client.put(
        "/api/v1/settings/embedding",
        json={"embedding_model": "m/embed", "embedding_api_key": "should-be-ignored"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["embedding_model"] == "m/embed"
    assert body["has_api_key"] is False


async def test_embedding_test_ok(
    async_client: AsyncClient,
) -> None:
    from app.main import app

    async def _mock_emb() -> EmbeddingClient:
        mock = AsyncMock(spec=EmbeddingClient)
        mock.embed.return_value = [0.1] * 1024
        return mock

    app.dependency_overrides[get_embedding_client] = _mock_emb
    try:
        resp = await async_client.post("/api/v1/settings/embedding/test")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        app.dependency_overrides.pop(get_embedding_client, None)
