"""ORM insert hooks so legacy tests can create Photo/PhotoAnalysis without meal_id."""

from __future__ import annotations

import datetime

from sqlalchemy import event, insert, select

from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis


from app.models.user import default_user_id


@event.listens_for(Photo, "before_insert")
def _create_meal_for_photo(_mapper, connection, target: Photo) -> None:
    if target.meal_id is not None:
        return
    owner_user_id = target.user_id if target.user_id is not None else default_user_id()
    meal_id = connection.execute(
        insert(Meal.__table__)
        .values(
            owner_user_id=owner_user_id,
            filename=target.filename,
            label=target.label,
            original_filename=target.original_filename,
            meal_time=target.meal_time,
            created_at=target.created_at or datetime.datetime.utcnow(),
        )
        .returning(Meal.__table__.c.id)
    ).scalar_one()
    target.meal_id = meal_id


@event.listens_for(PhotoAnalysis, "before_insert")
def _ensure_analysis_meal_id(_mapper, connection, target: PhotoAnalysis) -> None:
    if target.meal_id is not None:
        return
    if target.photo_id is None:
        raise ValueError("PhotoAnalysis requires meal_id or photo_id")
    meal_id = connection.execute(
        select(Photo.__table__.c.meal_id).where(Photo.__table__.c.id == target.photo_id)
    ).scalar_one()
    target.meal_id = meal_id
