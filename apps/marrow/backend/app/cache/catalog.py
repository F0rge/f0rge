from __future__ import annotations

import uuid
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from app.cache import redis_client
from app.cache.keys import catalog_key
from app.config import settings

T = TypeVar("T")


async def get_cached_catalog_list(
    user_id: uuid.UUID,
    kind: str,
    include_archived: bool,
    fetch: Callable[[], Any],
    response_model: type[BaseModel],
) -> list[T]:
    key = catalog_key(user_id, kind, include_archived)
    cached = await redis_client.get(key)
    if cached is not None:
        rows = redis_client.loads_json(cached)
        return [response_model.model_validate(row) for row in rows]  # type: ignore[return-value]

    items = await fetch()
    payload = [response_model.model_validate(item).model_dump(mode="json") for item in items]
    await redis_client.set(
        key,
        redis_client.dumps_json(payload),
        settings.cache_ttl_catalog_seconds,
    )
    return items


async def invalidate_catalog(user_id: uuid.UUID, kind: str) -> None:
    await redis_client.delete(catalog_key(user_id, kind, False))
    await redis_client.delete(catalog_key(user_id, kind, True))
