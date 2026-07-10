from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ExternalServiceError
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    EmbeddingSettingsUpdate,
    ExternalTokenResponse,
    LLMSettingsUpdate,
    SettingsResponse,
    TestConnectionResponse,
)
from app.services.llm.base import EmbeddingClient, LLMClient
from app.services.llm.encryption import encrypt
from app.tenant import current_user_id, owned_by_user


class SettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_or_create_row(self) -> UserSettings:
        result = await self.db.execute(
            select(UserSettings).where(owned_by_user(UserSettings.user_id))
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = UserSettings(user_id=current_user_id())
            self.db.add(row)
            await self.db.flush()
        return row

    @staticmethod
    def _to_response(row: UserSettings) -> SettingsResponse:
        return SettingsResponse(
            llm_provider=row.llm_provider,
            llm_model=row.llm_model,
            embedding_provider=row.embedding_provider,
            embedding_model=row.embedding_model,
            has_api_key=row.llm_api_key_encrypted is not None,
            has_external_api_token=row.external_api_token_encrypted is not None,
        )

    async def get(self) -> SettingsResponse:
        result = await self.db.execute(
            select(UserSettings).where(owned_by_user(UserSettings.user_id))
        )
        row = result.scalar_one_or_none()
        if row is None:
            return SettingsResponse(
                llm_provider="openrouter",
                llm_model=None,
                embedding_provider="openrouter",
                embedding_model=None,
                has_api_key=False,
                has_external_api_token=False,
            )
        return self._to_response(row)

    async def update_llm(self, data: LLMSettingsUpdate) -> SettingsResponse:
        row = await self._get_or_create_row()
        if data.llm_provider is not None:
            row.llm_provider = data.llm_provider
        if data.llm_api_key is not None:
            row.llm_api_key_encrypted = encrypt(data.llm_api_key)
        if data.llm_model is not None:
            row.llm_model = data.llm_model
        await self.db.commit()
        await self.db.refresh(row)
        return self._to_response(row)

    async def update_embedding(self, data: EmbeddingSettingsUpdate) -> SettingsResponse:
        row = await self._get_or_create_row()
        if data.embedding_provider is not None:
            row.embedding_provider = data.embedding_provider
        if data.embedding_model is not None:
            row.embedding_model = data.embedding_model
        await self.db.commit()
        await self.db.refresh(row)
        return self._to_response(row)

    async def regenerate_external_token(self) -> ExternalTokenResponse:
        """Generate a new external API token, encrypt and store it, return the plaintext once."""
        row = await self._get_or_create_row()
        plaintext = secrets.token_urlsafe(32)
        row.external_api_token_encrypted = encrypt(plaintext)
        await self.db.commit()
        await self.db.refresh(row)
        return ExternalTokenResponse(token=plaintext)

    async def revoke_external_token(self) -> SettingsResponse:
        """Clear the external API token, disabling all Bearer-token access."""
        row = await self._get_or_create_row()
        row.external_api_token_encrypted = None
        await self.db.commit()
        await self.db.refresh(row)
        return self._to_response(row)

    async def test_llm(self, llm: LLMClient) -> TestConnectionResponse:
        try:
            await llm.complete([{"role": "user", "content": "hi"}], max_tokens=1)
            return TestConnectionResponse(ok=True)
        except ExternalServiceError as exc:
            return TestConnectionResponse(ok=False, detail=exc.detail)

    async def test_embedding(self, emb: EmbeddingClient) -> TestConnectionResponse:
        try:
            await emb.embed("hi")
            return TestConnectionResponse(ok=True)
        except ExternalServiceError as exc:
            return TestConnectionResponse(ok=False, detail=exc.detail)
