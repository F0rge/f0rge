from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.channel import ChannelApiKeyCRUD
from app.models.channel import ChannelApiKey
from app.schemas.channel import ChannelApiKeyCreated, ChannelApiKeyResponse
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work

KEY_PREFIX = "velch_live_"


def hash_channel_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ChannelApiKeyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = ChannelApiKeyCRUD(db)

    async def list(self) -> list[ChannelApiKeyResponse]:
        return [self._to_response(row) for row in await self.crud.list_all()]

    async def create(self, name: str, user_id: uuid.UUID) -> ChannelApiKeyCreated:
        raw = secrets.token_urlsafe(32)
        token = f"{KEY_PREFIX}{raw}"
        row = ChannelApiKey(
            name=name.strip(),
            key_prefix=token[:16],
            key_hash=hash_channel_key(token),
            created_by_user_id=user_id,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(row)
        return ChannelApiKeyCreated(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            token=token,
            created_at=row.created_at,
        )

    async def revoke(self, key_id: uuid.UUID) -> ChannelApiKeyResponse:
        row = await self.crud.get_by_id(key_id)
        if row is None:
            raise NotFoundError("API key not found")
        async with unit_of_work(self.db):
            row.revoked_at = datetime.utcnow()
        return self._to_response(row)

    async def authenticate(self, token: str) -> Optional[uuid.UUID]:
        row = await self.crud.get_by_hash(hash_channel_key(token.strip()))
        if row is None or row.revoked_at is not None:
            return None
        row.last_used_at = datetime.utcnow()
        await self.db.flush()
        return row.created_by_user_id

    @staticmethod
    def _to_response(row: ChannelApiKey) -> ChannelApiKeyResponse:
        return ChannelApiKeyResponse(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
            revoked_at=row.revoked_at,
        )
