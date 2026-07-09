from __future__ import annotations

import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse

from app.dependencies.photos import get_photo_service
from app.middleware.auth import get_current_session
from app.models.photo import Photo
from app.schemas.photo import PhotoResponse, PhotoUpdate
from app.services.photos import PhotoService

router = APIRouter(
    prefix="/api/v1",
    tags=["photos"],
    dependencies=[Depends(get_current_session)],
)


@router.post(
    "/entries/{date}/photos",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    date: datetime.date,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    label: Optional[str] = Form(None),
    meal_time: Optional[datetime.datetime] = Form(None),
    service: PhotoService = Depends(get_photo_service),
) -> Photo:
    return await service.upload(date, file, label, meal_time, background_tasks)


@router.get("/photos/{photo_id}/file", response_model=None)
async def serve_photo(
    photo_id: int,
    service: PhotoService = Depends(get_photo_service),
) -> FileResponse | RedirectResponse:
    target = await service.get_file_path(photo_id)
    if target.startswith("http://") or target.startswith("https://"):
        return RedirectResponse(target)
    return FileResponse(target, media_type="image/jpeg")


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_photo(
    photo_id: int,
    service: PhotoService = Depends(get_photo_service),
) -> None:
    await service.delete(photo_id)


@router.patch("/photos/{photo_id}", response_model=PhotoResponse)
async def update_photo(
    photo_id: int,
    data: PhotoUpdate,
    service: PhotoService = Depends(get_photo_service),
) -> Photo:
    return await service.update_photo(photo_id, data)
