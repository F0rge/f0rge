from __future__ import annotations

import datetime
import uuid

from app.cache import redis_client
from app.cache.keys import entry_key, feature_matrix_prefix, signals_prefix


async def invalidate_entry_cache(user_id: uuid.UUID, date: datetime.date) -> None:
    await redis_client.delete(entry_key(user_id, date))


async def invalidate_feature_matrix_cache(user_id: uuid.UUID) -> None:
    await redis_client.delete_pattern(f"{feature_matrix_prefix(user_id)}*")


async def invalidate_signals_cache(user_id: uuid.UUID) -> None:
    await redis_client.delete_pattern(f"{signals_prefix(user_id)}*")


async def invalidate_user_insights_cache(user_id: uuid.UUID, date: datetime.date) -> None:
    await invalidate_entry_cache(user_id, date)
    await invalidate_feature_matrix_cache(user_id)
    await invalidate_signals_cache(user_id)
