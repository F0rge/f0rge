from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@dataclass
class CsvSession:
    data: list[dict[str, Any]]
    price_columns: list[str]
    product_codes: list[str]


# In-process session store — single-instance Coolify deploy; avoids shipping
# full CSV JSON back on every PDF request.
_sessions: dict[str, CsvSession] = {}


def create_session(
    data: list[dict[str, Any]],
    price_columns: list[str],
    product_codes: list[str],
) -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = CsvSession(
        data=data,
        price_columns=price_columns,
        product_codes=product_codes,
    )
    return session_id


def get_session(session_id: str) -> CsvSession | None:
    return _sessions.get(session_id)


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
