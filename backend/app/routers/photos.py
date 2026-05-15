from __future__ import annotations

import datetime
import os
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.entry import Entry
from app.models.photo import Photo
from app.schemas.photo import PhotoResponse
from app.services.obsidian import write_daily_file
from app.services.food_analysis import trigger_analysis_background
from app.services.photo_storage import delete_photo, resize_image, save_photo

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
    db: Session = Depends(get_db),
) -> Photo:
    entry = db.query(Entry).filter(Entry.date == date).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entry for {date}",
        )

    # Determine next photo number for this date.
    #
    # We can't use COUNT here: after a photo is deleted, the count drops
    # but the surviving photos keep their original numbers. Reusing a
    # number would collide with an existing filename on disk and silently
    # overwrite it (and produce two DB rows pointing at the same file).
    #
    # Instead, parse the photo_number from every existing filename for
    # this entry and take max() + 1. Deleted numbers stay permanently
    # retired -- gaps in the sequence are fine and intentional.
    prefix = f"{date.isoformat()}_photo-"
    suffix = ".jpg"
    used_numbers: set[int] = set()
    for (existing_filename,) in db.query(Photo.filename).filter(
        Photo.entry_id == entry.id
    ):
        if existing_filename.startswith(prefix) and existing_filename.endswith(suffix):
            try:
                used_numbers.add(int(existing_filename[len(prefix) : -len(suffix)]))
            except ValueError:
                # Filename has the right prefix/suffix but a non-numeric
                # middle (shouldn't happen, but don't crash uploads).
                pass
    photo_number = max(used_numbers, default=0) + 1

    filename = f"{prefix}{photo_number}{suffix}"

    # Read and process the uploaded file
    raw_bytes = await file.read()
    processed_bytes = resize_image(raw_bytes)

    # Save to both locations
    save_photo(processed_bytes, filename, settings.vault_path)

    # Create DB record
    photo = Photo(
        entry_id=entry.id,
        filename=filename,
        label=label,
        original_filename=file.filename,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    # Re-write vault file to include new photo
    db.refresh(entry)
    write_daily_file(db, entry, entry.photos)

    # Only queue analysis if the feature is enabled AND configured. Skipping
    # at the router avoids spinning up a background task that would only fail
    # in trigger_analysis_background. The latter still has its own guard for
    # robustness if the key is removed mid-upload.
    if settings.food_analysis_enabled and settings.openrouter_api_key:
        background_tasks.add_task(trigger_analysis_background, photo.id)

    return photo


@router.get("/photos/{photo_id}/file")
def serve_photo(photo_id: int, db: Session = Depends(get_db)) -> FileResponse:
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    photo_dir = os.path.abspath(settings.photo_dir)
    file_path = os.path.join(photo_dir, photo.filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo file not found",
        )

    return FileResponse(file_path, media_type="image/jpeg")


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo(photo_id: int, db: Session = Depends(get_db)) -> None:
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    entry = photo.entry

    # Delete files from both locations
    delete_photo(photo.filename, settings.vault_path)

    # Delete DB record
    db.delete(photo)
    db.commit()

    # Re-write vault file without the deleted photo
    db.refresh(entry)
    write_daily_file(db, entry, entry.photos)
