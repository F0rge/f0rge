from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_account_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.services.accounts import AccountService

accounts_router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@accounts_router.get("", response_model=list[AccountResponse])
async def list_accounts(
    _: uuid.UUID = Depends(get_current_user_id),
    service: AccountService = Depends(get_account_service),
):
    return await service.list()


@accounts_router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: AccountService = Depends(get_account_service),
):
    return await service.create(body)


@accounts_router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: AccountService = Depends(get_account_service),
):
    return await service.update(account_id, body)
