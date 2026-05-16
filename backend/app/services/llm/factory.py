from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import ConflictError
from app.models.user_settings import UserSettings
from app.services.llm.base import EmbeddingClient, LLMClient
from app.services.llm.encryption import decrypt
from app.services.llm.openrouter import OpenRouterClient, OpenRouterEmbeddingClient

_DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"


async def _load_user_settings(db: AsyncSession) -> UserSettings | None:
    result = await db.execute(select(UserSettings).where(UserSettings.id == 1))
    return result.scalar_one_or_none()


def _resolve(
    row: UserSettings | None,
    *,
    key_attr: str,
    model_attr: str,
    default_model: str,
) -> tuple[str | None, str]:
    """Resolution order: DB-stored encrypted key → env-var OPENROUTER_API_KEY → None.
    Custom model from DB overrides the default."""
    api_key: str | None = None
    model = default_model
    if row is not None:
        encrypted = getattr(row, key_attr)
        if encrypted:
            api_key = decrypt(encrypted)
        custom_model = getattr(row, model_attr)
        if custom_model:
            model = custom_model
    if api_key is None:
        api_key = settings.openrouter_api_key or None
    return (api_key, model)


async def resolve_llm_credentials(db: AsyncSession) -> tuple[str | None, str]:
    """Return (api_key, model) for the LLM provider. Callers handle missing key."""
    row = await _load_user_settings(db)
    return _resolve(
        row,
        key_attr="llm_api_key_encrypted",
        model_attr="llm_model",
        default_model=settings.openrouter_model,
    )


async def resolve_embedding_credentials(db: AsyncSession) -> tuple[str | None, str]:
    """Return (api_key, model) for the embedding provider. Callers handle missing key."""
    row = await _load_user_settings(db)
    return _resolve(
        row,
        key_attr="embedding_api_key_encrypted",
        model_attr="embedding_model",
        default_model=_DEFAULT_EMBEDDING_MODEL,
    )


async def get_llm_client(db: AsyncSession = Depends(get_db)) -> LLMClient:
    api_key, model = await resolve_llm_credentials(db)
    if not api_key:
        raise ConflictError("LLM not configured. Set an API key in /settings.")
    return OpenRouterClient(api_key=api_key, default_model=model)


async def get_embedding_client(db: AsyncSession = Depends(get_db)) -> EmbeddingClient:
    api_key, model = await resolve_embedding_credentials(db)
    if not api_key:
        raise ConflictError(
            "Embedding client not configured. Set an API key in /settings."
        )
    return OpenRouterEmbeddingClient(api_key=api_key, default_model=model)
