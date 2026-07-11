from __future__ import annotations

import uuid

AVATAR_COUNT = 32


def default_avatar_index(user_id: uuid.UUID) -> int:
    return user_id.int % AVATAR_COUNT
