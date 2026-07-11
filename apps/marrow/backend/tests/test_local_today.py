from __future__ import annotations

import datetime

import pytest

from app.config import settings
from app.utils.dates import local_today


def test_luxembourg_summer_midnight_window_diverges_from_utc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 23:30 UTC on Jul 3 == 01:30 CEST (UTC+2) on Jul 4 in Luxembourg.
    now = datetime.datetime(2026, 7, 3, 23, 30, tzinfo=datetime.timezone.utc)

    monkeypatch.setattr(settings, "app_timezone", "Europe/Luxembourg")
    assert local_today(now) == datetime.date(2026, 7, 4)

    # Same instant, UTC setting: proves the function reads the setting, not a
    # hardcoded zone.
    monkeypatch.setattr(settings, "app_timezone", "UTC")
    assert local_today(now) == datetime.date(2026, 7, 3)


def test_luxembourg_winter_cet_offset_also_crosses_midnight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 23:15 UTC on Jan 14 == 00:15 CET (UTC+1) on Jan 15 in Luxembourg.
    now = datetime.datetime(2026, 1, 14, 23, 15, tzinfo=datetime.timezone.utc)

    monkeypatch.setattr(settings, "app_timezone", "Europe/Luxembourg")
    assert local_today(now) == datetime.date(2026, 1, 15)


def test_no_arg_path_resolves_without_error() -> None:
    result = local_today()
    assert isinstance(result, datetime.date)
