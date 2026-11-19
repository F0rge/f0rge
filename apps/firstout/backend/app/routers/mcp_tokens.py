from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import require_directory_tenant
from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.schemas.mcp_token import McpAccessResponse, McpTokenCreate, McpTokenIssued, McpTokenRotate
from app.services.mcp_tokens import McpTokenService

router = APIRouter(prefix="/api/v1/mcp-tokens", tags=["mcp-tokens"])


def get_mcp_token_service(
    _user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> McpTokenService:
    return McpTokenService(db, require_directory_tenant())


CurrentUser = Annotated[uuid.UUID, Depends(get_current_user_id)]
TokenService = Annotated[McpTokenService, Depends(get_mcp_token_service)]


@router.get("")
async def list_tokens(user_id: CurrentUser, service: TokenService) -> McpAccessResponse:
    return await service.list(user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_token(
    body: McpTokenCreate, response: Response, user_id: CurrentUser, service: TokenService
) -> McpTokenIssued:
    response.headers["Cache-Control"] = "no-store"
    return await service.create(user_id, body)


@router.post("/{token_id}/rotate")
async def rotate_token(
    token_id: uuid.UUID,
    body: McpTokenRotate,
    response: Response,
    user_id: CurrentUser,
    service: TokenService,
) -> McpTokenIssued:
    response.headers["Cache-Control"] = "no-store"
    return await service.rotate(user_id, token_id, body.version)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(token_id: uuid.UUID, user_id: CurrentUser, service: TokenService) -> None:
    await service.revoke(user_id, token_id)
