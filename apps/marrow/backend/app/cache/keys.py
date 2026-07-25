from __future__ import annotations

import datetime
import uuid

CATALOG_KINDS = frozenset({"supplements", "medications", "diet_tags", "symptoms", "trackers"})


def _bound_token(value: datetime.date | None) -> str:
    return value.isoformat() if value is not None else "none"


def catalog_key(user_id: uuid.UUID, kind: str, include_archived: bool = False) -> str:
    suffix = "all" if include_archived else "active"
    return f"u:{user_id}:catalog:{kind}:{suffix}"


def entry_key(user_id: uuid.UUID, date: datetime.date) -> str:
    return f"u:{user_id}:entry:{date.isoformat()}"


def feature_matrix_key(
    user_id: uuid.UUID,
    start: datetime.date | None,
    end: datetime.date | None,
) -> str:
    from app.services.feature_matrix import FEATURE_SCHEMA_VERSION

    return f"u:{user_id}:fm:v{FEATURE_SCHEMA_VERSION}:{_bound_token(start)}:{_bound_token(end)}"


def feature_matrix_prefix(user_id: uuid.UUID) -> str:
    return f"u:{user_id}:fm:"


def signals_key(
    user_id: uuid.UUID,
    outcome: str,
    start: datetime.date | None,
    end: datetime.date | None,
) -> str:
    from app.services.signals.service import SIGNALS_SCHEMA_VERSION

    return (
        f"u:{user_id}:signals:v{SIGNALS_SCHEMA_VERSION}:"
        f"{outcome}:{_bound_token(start)}:{_bound_token(end)}"
    )


def signals_prefix(user_id: uuid.UUID) -> str:
    return f"u:{user_id}:signals:"
