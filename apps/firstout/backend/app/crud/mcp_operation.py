from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_operation import McpOperation
from app.models.mcp_token import McpToken
from f0rge_db.crud import BaseCRUD


class McpOperationCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
        super().__init__(db)
        self.owner = (McpOperation.team_id == team_id, McpOperation.user_id == user_id)

    async def by_request(self, token: McpToken, request_id: uuid.UUID) -> McpOperation | None:
        return await self.db.scalar(
            select(McpOperation).where(
                *self.owner,
                McpOperation.token_id == token.id,
                McpOperation.request_id == request_id,
            )
        )

    async def review_token(self, operation_id: uuid.UUID) -> uuid.UUID | None:
        return await self.db.scalar(
            select(McpOperation.token_id).where(
                *self.owner,
                McpOperation.id == operation_id,
                McpOperation.preview.is_not(None),
            )
        )

    async def review(self, operation_id: uuid.UUID) -> McpOperation:
        return (
            await self.db.scalars(
                select(McpOperation).where(
                    *self.owner,
                    McpOperation.id == operation_id,
                    McpOperation.preview.is_not(None),
                )
            )
        ).one()
