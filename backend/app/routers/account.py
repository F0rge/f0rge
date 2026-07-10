from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.dependencies.account import get_account_service
from app.middleware.auth import get_current_session
from app.schemas.account import (
    AccountDeleteRequest,
    AccountResponse,
    AccountUpdate,
    PasswordChangeRequest,
)
from app.services.account import AccountService

router = APIRouter(
    prefix="/api/v1/account",
    tags=["account"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=AccountResponse)
async def get_account(
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    return await service.get()


@router.patch("", response_model=AccountResponse)
async def update_account(
    data: AccountUpdate,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    return await service.update(data)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChangeRequest,
    service: AccountService = Depends(get_account_service),
) -> None:
    return await service.change_password(data)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: AccountDeleteRequest,
    response: Response,
    service: AccountService = Depends(get_account_service),
) -> None:
    return await service.delete(data, response)
