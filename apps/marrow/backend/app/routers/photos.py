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
from app.dependencies.meal_tags import get_meal_tag_service
from app.middleware.auth import get_current_session
from app.models.photo import Photo
from app.schemas.photo import PhotoResponse, PhotoUpdate
from app.schemas.social import PhotoMealTagListResponse, PhotoTagRequest
from app.services.meal_tags import MealTagService
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
    tagged_handles: Optional[str] = Form(None),
    tagged_group_ids: Optional[str] = Form(None),
    service: PhotoService = Depends(get_photo_service),
) -> PhotoResponse:
    return await service.upload(
        date, file, label, meal_time, background_tasks, tagged_handles, tagged_group_ids
    )


@router.get("/photos/{photo_id}/file", response_model=None)
async def serve_photo(
    photo_id: int,
    service: PhotoService = Depends(get_photo_service),
) -> FileResponse | RedirectResponse:
    return await service.serve_photo_file(photo_id)


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


@router.get("/photos/{photo_id}/tags", response_model=PhotoMealTagListResponse)
async def list_photo_tags(
    photo_id: int,
    service: MealTagService = Depends(get_meal_tag_service),
):
    return await service.list_tags_for_photo(photo_id)


@router.post("/photos/{photo_id}/tags", response_model=PhotoMealTagListResponse)
async def add_photo_tags(
    photo_id: int,
    body: PhotoTagRequest,
    service: MealTagService = Depends(get_meal_tag_service),
):
    return await service.add_tags_to_photo(photo_id, body.handles, body.group_ids)
