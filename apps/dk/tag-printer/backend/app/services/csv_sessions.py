from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
SESSION_TTL_SECONDS = 60 * 60  # 1 hour


@dataclass
class CsvSession:
    data: list[dict[str, Any]]
    price_columns: list[str]
    product_codes: list[str]
    created_at: float = field(default_factory=time.monotonic)


# In-process session store — single-instance Coolify deploy; avoids shipping
# full CSV JSON back on every PDF request.
_sessions: dict[str, CsvSession] = {}


def _purge_stale() -> None:
    cutoff = time.monotonic() - SESSION_TTL_SECONDS
    for session_id, session in list(_sessions.items()):
        if session.created_at < cutoff:
            _sessions.pop(session_id, None)


def create_session(
    data: list[dict[str, Any]],
    price_columns: list[str],
    product_codes: list[str],
) -> str:
    _purge_stale()
    session_id = str(uuid.uuid4())
    _sessions[session_id] = CsvSession(
        data=data,
        price_columns=price_columns,
        product_codes=product_codes,
    )
    return session_id


def get_session(session_id: str) -> CsvSession | None:
    _purge_stale()
    return _sessions.get(session_id)


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
