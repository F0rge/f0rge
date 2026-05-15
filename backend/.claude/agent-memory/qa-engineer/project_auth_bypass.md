---
name: Auth bypass for Playwright e2e
description: Insert auth_sessions row directly + set ht_session cookie via JS to skip PIN flow
type: project
---

Auth is PIN-based with bcrypt; the PIN isn't easily reproducible from env. For Playwright tests, bypass the login flow entirely:

```python
import secrets, datetime
from sqlalchemy.orm import Session
from app.database import engine
from app.models.session import AuthSession

token = secrets.token_urlsafe(32)
expires = datetime.datetime.utcnow() + datetime.timedelta(days=30)
with Session(engine) as s:
    s.add(AuthSession(token=token, created_at=datetime.datetime.utcnow(), expires_at=expires))
    s.commit()
print(token)
```

Run via `cd backend && uv run python -c "..."`. Then in the browser:
- Navigate to any frontend page first (so the cookie can attach to the right origin).
- `document.cookie = 'ht_session=<token>; path=/; SameSite=Lax'` via `browser_evaluate`.

**Important:** the backend sets `ht_session` as **HttpOnly**, so `document.cookie` cannot READ it back. The cookie is still sent on subsequent fetches — confirm by hitting `/api/v1/auth/me` with `credentials: 'include'` and checking the response.

**How to apply:** use this every time the QA gate needs Playwright auth. Don't try to scrape the PIN from the user.
