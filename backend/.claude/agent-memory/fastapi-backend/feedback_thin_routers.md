---
name: Thin routers — non-negotiable
description: FastAPI routers must be 1-3 lines per endpoint with no logic; pre-existing violations don't excuse new ones
type: feedback
---

Routers are strictly thin: HTTP mapping ONLY. Each endpoint is 1-3 lines: signature, optional one-line delegation, and `return`.

**Banned in router functions:** `if`/`else`/ternary, `try`/`except`, `raise` (including `HTTPException`), loops, direct ORM queries, direct DB session access, helper functions defined in the router module, inline business logic of any kind.

**Why:** Architectural contract Leo enforces project-wide. Pre-existing violations are not an excuse — new code must always follow this pattern. If you see violations in an existing router, refactor or open a follow-up; never copy the pattern.

**How to apply:** All validation, normalization, side effects, and exception raising live in services. Services raise domain exceptions from `app/exceptions.py`; global handlers in `app/main.py` map them to HTTP. The router never touches `HTTPException`.
