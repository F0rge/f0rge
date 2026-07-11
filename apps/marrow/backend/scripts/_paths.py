"""Resolve where the dietary reference JSON files live.

Used by the load scripts so they can read from the bundled image path in
Docker (set via DIETARY_DATA_DIR env var) and fall back to the repo's
backend/data/ for local dev.
"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Directory containing the dietary reference JSON files."""
    override = os.environ.get("DIETARY_DATA_DIR")
    if override:
        return Path(override)
    # Repo layout: this file is at backend/scripts/_paths.py; data lives at
    # backend/data/.
    return Path(__file__).resolve().parent.parent / "data"
