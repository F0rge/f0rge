from __future__ import annotations

import datetime
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.settings import UserSettingsCRUD
from f0rge_core.exceptions import ExternalServiceError
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    CheckinDefaultsUpdate,
    EmbeddingSettingsUpdate,
    ExternalTokenResponse,
    LLMSettingsUpdate,
    ProfileTagFilterUpdate,
    SettingsResponse,
    TestConnectionResponse,
)
from app.services.llm.base import EmbeddingClient, LLMClient
from app.services.llm.encryption import encrypt, hash_external_api_token
from f0rge_db.tenant import current_user_id


class SettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserSettingsCRUD(db)

    async def _get_or_create_row(self) -> UserSettings:
        row = await self.crud.get()
        if row is None:
            row = UserSettings(user_id=current_user_id())
            self.crud.add(row)
            await self.crud.flush()
        return row

    @staticmethod
    def _to_response(row: UserSettings) -> SettingsResponse:
        return SettingsResponse(
            llm_provider=row.llm_provider,
            llm_model=row.llm_model,
            embedding_provider=row.embedding_provider,
            embedding_model=row.embedding_model,
            has_api_key=row.llm_api_key_encrypted is not None,
            # Auth uses hash lookup; report presence from hash so a failed
            # migration backfill cannot show "active" while MCP rejects the token.
            has_external_api_token=row.external_api_token_hash is not None,
            onboarding_completed=row.onboarding_completed_at is not None,
            tagged_meal_mode=row.tagged_meal_mode,
            profile_tag_filter_mode=row.profile_tag_filter_mode,
            profile_filter_tags=row.profile_filter_tags_list,
            default_supplements=row.default_supplements_list,
            default_symptoms=dict(row.default_symptoms_json or {}),
        )

    async def get(self) -> SettingsResponse:
        row = await self.crud.get()
        if row is None:
            return SettingsResponse(
                llm_provider="openrouter",
                llm_model=None,
                embedding_provider="openrouter",
                embedding_model=None,
                has_api_key=False,
                has_external_api_token=False,
                onboarding_completed=False,
                tagged_meal_mode="approve",
                profile_tag_filter_mode="off",
                profile_filter_tags=[],
                default_supplements=[],
                default_symptoms={},
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
        row = await self.crud.commit_refresh(row)
        return self._to_response(row)

    async def update_embedding(self, data: EmbeddingSettingsUpdate) -> SettingsResponse:
        row = await self._get_or_create_row()
        if data.embedding_provider is not None:
            row.embedding_provider = data.embedding_provider
        if "embedding_model" in data.model_fields_set:
            row.embedding_model = data.embedding_model
        row = await self.crud.commit_refresh(row)
        return self._to_response(row)

    async def regenerate_external_token(self) -> ExternalTokenResponse:
        """Generate a new external API token, encrypt and store it, return the plaintext once."""
        row = await self._get_or_create_row()
        plaintext = secrets.token_urlsafe(32)
        row.external_api_token_encrypted = encrypt(plaintext)
        row.external_api_token_hash = hash_external_api_token(plaintext)
        await self.crud.commit_refresh(row)
        return ExternalTokenResponse(token=plaintext)

    async def revoke_external_token(self) -> SettingsResponse:
        """Clear the external API token, disabling all Bearer-token access."""
        row = await self._get_or_create_row()
        row.external_api_token_encrypted = None
        row.external_api_token_hash = None
        row = await self.crud.commit_refresh(row)
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

    async def complete_onboarding(self) -> SettingsResponse:
        row = await self._get_or_create_row()
        if row.onboarding_completed_at is None:
            row.onboarding_completed_at = datetime.datetime.utcnow()
            row = await self.crud.commit_refresh(row)
        return self._to_response(row)

    async def update_tagged_meal_mode(self, mode: str) -> SettingsResponse:
        row = await self._get_or_create_row()
        row.tagged_meal_mode = mode
        row = await self.crud.commit_refresh(row)
        return self._to_response(row)

    async def update_profile_tag_filter(self, data: ProfileTagFilterUpdate) -> SettingsResponse:
        row = await self._get_or_create_row()
        row.profile_tag_filter_mode = data.profile_tag_filter_mode
        row.profile_filter_tags = ",".join(data.profile_filter_tags)
        row = await self.crud.commit_refresh(row)
        return self._to_response(row)

    async def update_checkin_defaults(self, data: CheckinDefaultsUpdate) -> SettingsResponse:
        row = await self._get_or_create_row()
        supplements = [k for k in data.default_supplements if k]
        row.default_supplements = ",".join(supplements)
        row.default_symptoms_json = dict(data.default_symptoms)
        row = await self.crud.commit_refresh(row)
        return self._to_response(row)
