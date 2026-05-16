from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.schemas.enriched import EnrichedDayResponse
from app.services.weather import get_daily_summary

router = APIRouter(
    prefix="/api/v1/enriched",
    tags=["enriched"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/{date}", response_model=EnrichedDayResponse)
def get_enriched_day(date: datetime.date, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.date == date).first()
    weather = get_daily_summary(db, date)
    health = db.query(HealthMetric).filter(HealthMetric.date == date).first()

    return EnrichedDayResponse(
        entry=entry,
        weather=weather,
        health_metrics=health,
    )
