from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.entry import Entry
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from app.services.obsidian import delete_daily_file, write_daily_file
from app.services.photo_storage import delete_photo

router = APIRouter(
    prefix="/api/v1/entries",
    tags=["entries"],
    dependencies=[Depends(get_current_session)],
)


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(body: EntryCreate, db: Session = Depends(get_db)):
    existing = db.query(Entry).filter(Entry.date == body.date).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entry for {body.date} already exists",
        )

    entry = Entry(**body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)

    write_daily_file(db, entry, entry.photos)

    return entry


@router.get("", response_model=list[EntryResponse])
def list_entries(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    query = db.query(Entry)

    if month:
        year, mon = month.split("-")
        start = datetime.date(int(year), int(mon), 1)
        if int(mon) == 12:
            end = datetime.date(int(year) + 1, 1, 1)
        else:
            end = datetime.date(int(year), int(mon) + 1, 1)
        query = query.filter(Entry.date >= start, Entry.date < end)

    return query.order_by(Entry.date.desc()).all()


@router.get("/{date}", response_model=EntryResponse)
def get_entry(date: datetime.date, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.date == date).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entry for {date}",
        )
    return entry


@router.put("/{date}", response_model=EntryResponse)
def update_entry(
    date: datetime.date, body: EntryUpdate, db: Session = Depends(get_db)
):
    entry = db.query(Entry).filter(Entry.date == date).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entry for {date}",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)

    write_daily_file(db, entry, entry.photos)

    return entry


@router.delete("/{date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(date: datetime.date, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.date == date).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entry for {date}",
        )

    # Delete associated photo files
    for photo in entry.photos:
        delete_photo(photo.filename, settings.vault_path)

    # Delete vault file
    delete_daily_file(entry.date.isoformat())

    # Delete DB record (cascades to photos)
    db.delete(entry)
    db.commit()
