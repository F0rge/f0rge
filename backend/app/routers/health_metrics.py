from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.health_metrics import HealthMetric
from app.models.session import AuthSession
from app.schemas.health_metrics import HealthMetricCreate, HealthMetricResponse
from app.services.health_import import parse_health_auto_export

router = APIRouter(
    prefix="/api/v1/health-metrics",
    tags=["health-metrics"],
)


def get_health_import_auth(
    authorization: Optional[str] = Header(default=None),
    ht_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> bool:
    """Accept either a valid session cookie OR a Bearer token matching
    the configured health_import_token."""
    # Try Bearer token first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if settings.health_import_token and token == settings.health_import_token:
            return True

    # Try session cookie
    if ht_session:
        session = (
            db.query(AuthSession).filter(AuthSession.token == ht_session).first()
        )
        if session and session.expires_at >= datetime.datetime.utcnow():
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


@router.post("/import", status_code=status.HTTP_200_OK)
def import_health_data(
    body: dict,
    db: Session = Depends(get_db),
    _auth: bool = Depends(get_health_import_auth),
):
    parsed = parse_health_auto_export(body)
    upserted = 0

    for date_key, metric_create in parsed.items():
        existing = (
            db.query(HealthMetric)
            .filter(HealthMetric.date == metric_create.date)
            .first()
        )
        if existing:
            update_data = metric_create.model_dump(exclude={"date"}, exclude_none=True)
            for field, value in update_data.items():
                setattr(existing, field, value)
        else:
            record = HealthMetric(**metric_create.model_dump())
            db.add(record)
        upserted += 1

    db.commit()
    return {"status": "ok", "dates_upserted": upserted}


@router.get(
    "/{date}",
    response_model=HealthMetricResponse,
    dependencies=[Depends(get_current_session)],
)
def get_health_metric(date: datetime.date, db: Session = Depends(get_db)):
    metric = (
        db.query(HealthMetric).filter(HealthMetric.date == date).first()
    )
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No health metrics for {date}",
        )
    return metric
