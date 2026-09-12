# Hypothesis scoreboard

User-scoped tracker for ranked questions, kill-tests, and status. This is a
log, not a diagnosis engine.

## Tables

`hypotheses` and `n_of_1_slots` are in `USER_OWNED_TABLES` with the same FORCE
RLS `tenant_isolation` policy as treatments, entries, and labs. Auth is the
existing `ht_session` cookie or bearer token. There is no public or signup
endpoint.

Killed rows are never hard-deleted. Change `status` to `killed` instead.

| Field | Notes |
| --- | --- |
| `slug` | Unique per user. Lowercase letters, digits, hyphens. |
| `status` | `live` \| `weakening` \| `killed` \| `parked` |
| `layer` | `1`, `2`, or null (the L3–L5 labels live in `title`/`slug`) |
| `n_of_1_slots` | At most one row per user (`change`, `start`, `watch_field`, `stop_rule`) |

## API

All routes require the same session/token gate as other health tables.

- `GET /api/v1/hypotheses?status=`
- `POST /api/v1/hypotheses`
- `GET /api/v1/hypotheses/{id}`
- `PUT /api/v1/hypotheses/{id}`
- `GET /api/v1/hypotheses/n-of-1`
- `PUT /api/v1/hypotheses/n-of-1`

No `DELETE`.

## MCP

Tools (token-scoped to the authenticated user):

- `list_hypotheses`
- `update_hypothesis` (id or slug; writes use the app role, not `healthtracker_ro`)
- `get_n_of_1`
- `update_n_of_1`

## Seed for handle `leo`

Migration `053` creates empty tables. It does **not** seed production.

After migrate, load the nine tracker rows for handle `leo`:

```bash
cd apps/marrow/backend
set -a && . ./.env && set +a
# Use a sync URL (strip +asyncpg) so psql/SQLAlchemy can run the DO block.
psql "${DATABASE_URL/+asyncpg/}" -v ON_ERROR_STOP=1 -f scripts/seed_leo_hypotheses.sql
```

The SQL no-ops-as-upsert on `(user_id, slug)` and raises if handle `leo` is missing.
