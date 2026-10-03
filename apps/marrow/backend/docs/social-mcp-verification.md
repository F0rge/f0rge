# Social layer — tenant isolation verification runbook

The MCP server no longer has a raw SQL tool (`read_sql` was removed in the public-surface rewrite),
so RLS checks for the social tables (`connections`, `meal_tags`, `notifications`, `groups`,
`group_members`) are done at the database and test level rather than through MCP. There is no
dev MCP/API deployment to run them against: Railway has a single production environment.

## 1. Role grants — `healthtracker_ro` can SELECT new tables

New social tables need explicit grants for the read-only role or read tools fail closed
(errors, not leaks). From a schema-admin psql session:

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

## 2. RLS isolation (CI)

CI enforces the tenant policies, including pre-approval meal-tag isolation and cross-user
notification reads:

```bash
cd apps/marrow/backend
uv run pytest tests/test_social_rls.py tests/test_tenant_isolation.py -v
```

The suite connects as `test_app` (NOSUPERUSER) and seeds cross-tenant fixtures via `superuser_engine`.

## 3. MCP spot check (optional, with a user's bearer token)

- `list_people` returns only that user's accepted connections.
- `get_day` for a date that only another user logged returns `null`.
- `get_meal` for another user's `photo_id` returns not-found.

## Record results

| Date | Migration | Operator | RO grants | pytest RLS | Notes |
|------|-----------|----------|-----------|------------|-------|
| | | | | | |
