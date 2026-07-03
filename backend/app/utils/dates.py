from __future__ import annotations

import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.config import settings


def local_today(now: Optional[datetime.datetime] = None) -> datetime.date:
    """Today's calendar date in app_timezone, not container UTC.

    Container has no TZ set, so date.today() silently reads UTC — wrong for a
    Luxembourg-local user between local midnight and the UTC offset catching
    up (e.g. until ~2am CEST). See frontend twin: lib/utils.ts formatLocalDate().
    """
    instant = now if now is not None else datetime.datetime.now(datetime.timezone.utc)
    return instant.astimezone(ZoneInfo(settings.app_timezone)).date()
