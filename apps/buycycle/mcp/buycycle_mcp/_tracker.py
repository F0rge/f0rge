"""Locate tracker/fees.py and tracker/market.py without importing the scraper."""

from __future__ import annotations

import sys
from pathlib import Path


def tracker_dir() -> Path:
    here = Path(__file__).resolve()
    # Repo layout: apps/buycycle/mcp/buycycle_mcp -> apps/buycycle/tracker
    # Image layout: /app/buycycle_mcp -> /app/tracker
    for base in (here.parents[2], here.parents[1]):
        candidate = base / "tracker"
        if (candidate / "fees.py").is_file() and (candidate / "market.py").is_file():
            return candidate
    raise RuntimeError("buycycle tracker modules fees.py and market.py were not found")


def ensure_tracker_on_path() -> Path:
    path = tracker_dir()
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return path
