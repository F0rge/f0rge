from __future__ import annotations

import uuid


def signup_payload(
    email: str,
    password: str,
    handle: str | None = None,
) -> dict[str, str]:
    local = email.split("@")[0].replace(".", "_").replace("-", "_")
    chosen = handle or (local if len(local) >= 3 else f"u_{uuid.uuid4().hex[:8]}")
    return {"email": email, "password": password, "handle": chosen}
