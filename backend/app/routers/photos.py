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
from fastapi.responses import FileResponse

from app.dependencies.photos import get_photo_service
from app.middleware.auth import get_current_session
from app.models.photo import Photo
from app.schemas.photo import PhotoMealTimeUpdate, PhotoResponse
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


@router.get("/photos/{photo_id}/file")
def serve_photo(
    photo_id: int,
    service: PhotoService = Depends(get_photo_service),
) -> FileResponse:
    return FileResponse(service.get_file_path(photo_id), media_type="image/jpeg")


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo(
    photo_id: int,
    service: PhotoService = Depends(get_photo_service),
) -> None:
    service.delete(photo_id)


@router.patch("/photos/{photo_id}", response_model=PhotoResponse)
def update_photo(
    photo_id: int,
    data: PhotoMealTimeUpdate,
    service: PhotoService = Depends(get_photo_service),
) -> Photo:
    return service.update_meal_time(photo_id, data.meal_time)
