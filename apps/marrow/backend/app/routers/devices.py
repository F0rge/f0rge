from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.devices import DeviceRegisterRequest, DeviceTokenResponse
from app.services import push

router = APIRouter(
    prefix="/api/v1/devices",
    tags=["devices"],
    dependencies=[Depends(get_current_session)],
)


@router.post("", response_model=DeviceTokenResponse)
async def register_device(
    body: DeviceRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    return await push.register_device(db, body.token, body.platform)


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    await push.unregister_device(db, token)
