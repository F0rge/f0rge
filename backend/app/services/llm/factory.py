from __future__ import annotations

from typing import Optional

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
from app.tenant import owned_by_user

DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"


async def load_user_settings(db: AsyncSession) -> Optional[UserSettings]:
    result = await db.execute(select(UserSettings).where(owned_by_user(UserSettings.user_id)))
    return result.scalar_one_or_none()


async def load_user_settings_singleton(db: AsyncSession) -> Optional[UserSettings]:
    return await load_user_settings(db)


def _resolve(
    row: Optional[UserSettings],
    *,
    key_attr: str,
    model_attr: str,
    default_model: str,
) -> tuple[Optional[str], str]:
    """Resolution order: DB-stored encrypted key → env-var OPENROUTER_API_KEY → None.
    Custom model from DB overrides the default."""
    api_key: Optional[str] = None
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


async def resolve_llm_credentials(db: AsyncSession) -> tuple[Optional[str], str]:
    """Return (api_key, model) for the LLM provider. Callers handle missing key."""
    row = await load_user_settings_singleton(db)
    return _resolve(
        row,
        key_attr="llm_api_key_encrypted",
        model_attr="llm_model",
        default_model=settings.openrouter_model,
    )


async def resolve_embedding_credentials(db: AsyncSession) -> tuple[Optional[str], str]:
    """Return (api_key, model) for the embedding provider. Callers handle missing key.

    Key resolution shares llm_api_key_encrypted with resolve_llm_credentials — there is
    only one stored BYOK key, used by both clients. Model resolution stays independent."""
    row = await load_user_settings_singleton(db)
    return _resolve(
        row,
        key_attr="llm_api_key_encrypted",
        model_attr="embedding_model",
        default_model=DEFAULT_EMBEDDING_MODEL,
    )


async def build_llm_client(db: AsyncSession) -> LLMClient:
    api_key, model = await resolve_llm_credentials(db)
    if not api_key:
        raise ConflictError("LLM not configured. Set an API key in /settings.")
    return OpenRouterClient(api_key=api_key, default_model=model)


async def build_embedding_client(db: AsyncSession) -> EmbeddingClient:
    api_key, model = await resolve_embedding_credentials(db)
    if not api_key:
        raise ConflictError("Embedding client not configured. Set an API key in /settings.")
    return OpenRouterEmbeddingClient(api_key=api_key, default_model=model)


async def get_llm_client(db: AsyncSession = Depends(get_db)) -> LLMClient:
    return await build_llm_client(db)


async def get_embedding_client(db: AsyncSession = Depends(get_db)) -> EmbeddingClient:
    return await build_embedding_client(db)
