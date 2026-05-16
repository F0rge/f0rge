from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.photos import PhotoService


def get_photo_service(db: Session = Depends(get_db)) -> PhotoService:
    return PhotoService(db)
