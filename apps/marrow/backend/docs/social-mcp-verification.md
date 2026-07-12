# Social layer — MCP `read_sql` verification runbook

Run after each social migration deploys to **dev** (`marrow-mcp-dev` / `marrow_dev` database).
Confirms `healthtracker_ro` can reach new tables and RLS isolates rows per MCP token user.

## Prerequisites

- Dev API healthy: `curl -sf https://api-dev.marrow-health.com/api/v1/health`
- Dev MCP healthy: `curl -sf https://marrow-mcp-dev.fly.dev/health` (or MCP health route)
- Two test accounts with MCP tokens (user A, user B) connected as accepted friends
- Fly deploy logs show `alembic upgrade head` succeeded on `marrow-dev` release command

## 1. Role grants — `healthtracker_ro` can SELECT new tables

On Fly MPG, `healthtracker_ro` is provisioned outside migration 004 default privileges.
New social tables need explicit grants or `read_sql` fails closed (errors, not leaks).

From a schema-admin/psql session on `marrow_dev`:

```sql
-- Repeat for each new social table after migration
GRANT SELECT ON connections TO healthtracker_ro;
GRANT SELECT ON meal_tags TO healthtracker_ro;
GRANT SELECT ON notifications TO healthtracker_ro;
GRANT SELECT ON groups TO healthtracker_ro;
GRANT SELECT ON group_members TO healthtracker_ro;
```

Smoke as `healthtracker_ro`:

```sql
SET ROLE healthtracker_ro;
SELECT count(*) FROM connections;
SELECT count(*) FROM notifications;
RESET ROLE;
```

**Pass:** queries succeed (counts may be zero). **Fail:** `permission denied` → grant missing.

## 2. MCP token scoping — user A sees only A's rows

With user A's MCP bearer token, call `read_sql`:

```sql
SELECT * FROM connections;
SELECT * FROM notifications;
SELECT * FROM group_members;
```

**Pass:** every `user_id` / party column references A only. **Fail:** any row belonging solely to B.

## 3. Pre-approval meal tag isolation (when `meal_tags` ships)

User B tags user A on a meal pending approval. With user A's token:

```sql
SELECT * FROM meal_tags WHERE recipient_id = '<A-uuid>';
```

**Pass:** zero rows until A approves. After approval via API, same query returns the tag.

## 4. Negative — user A cannot read B's private notifications

```sql
SELECT * FROM notifications WHERE user_id = '<B-uuid>';
```

**Pass:** zero rows. Direct cross-user `user_id` in WHERE must not bypass RLS.

## 5. Deploy checklist

| Step | Command / check |
|------|-----------------|
| Migration ran | `fly logs -a marrow-dev` → `alembic upgrade head` without error |
| API release | `curl -sf https://api-dev.marrow-health.com/api/v1/health` |
| MCP release | MCP health endpoint 200 |
| RO grants | Step 1 psql smoke |
| RLS smoke | Steps 2–4 via MCP `read_sql` |

## Local pytest equivalent

CI enforces the same policies without MCP:

```bash
cd apps/marrow/backend
uv run pytest tests/test_social_rls.py -v
```

The suite connects as `test_app` (NOSUPERUSER) and seeds cross-tenant fixtures via `superuser_engine`.

## Record results

| Date | Migration | Operator | RO grants | A-token scope | B-meal pre-approval | Notes |
|------|-----------|----------|-----------|---------------|---------------------|-------|
| | | | | | | |
