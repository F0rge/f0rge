# Cutover runbook — SQLite → Postgres (#46 + #47)

This runbook is executed by Leo (or an orchestrator session) on the day of
cutover. It assumes the combined PR (#46 + #47) is reviewed and ready to merge,
the migration script (`backend/scripts/migrate_sqlite_to_postgres.py`) has
already been validated against an rsync'd copy of the live SQLite DB, and the
Pi is reachable via `ssh leo@rpi`.

Estimated wall-clock: **~15 min** end-to-end (10 min cutover + 5 min smoke).

Coolify backend app UUID: `mk404cskowkgcow48g8s8okw`.
Coolify frontend app UUID: stays on `build_pack=dockerfile` — do not touch.

Conventions used below:
- `$TOKEN` — a Coolify Sanctum API token (see step 0.1)
- `$PG_PASSWORD` — never appears in commands; fetched at runtime from the running container
- Commands marked **[CONFIRM]** require explicit user go-ahead before running
- Both **REST API (Option A)** and **tinker (Option B)** paths are documented;
  pick one per step

---

## 0. Pre-flight (do these BEFORE merging the PR)

### 0.1 Generate (or reuse) a Coolify API token

UI path: open `https://coolify.taxpilot.lu` → Profile (top-right) →
Keys & Tokens → API Tokens → "Create New Token". Scopes needed: **read,
write, deploy, read-sensitive**. Save the plaintext token into a temporary
shell variable on your laptop:

```bash
export TOKEN='paste-the-token-here'
```

If you'd rather skip the UI, use the direct-insert tinker recipe documented in
`~/.claude/agents/devops` CLAUDE.md (it writes a row into
`personal_access_tokens` with `team_id=0` and ability `["*"]`). This is also
the fallback if the UI is unreachable.

### 0.2 Verify required env vars exist on the backend app

The compose file references `${POSTGRES_PASSWORD}` and
`${SETTINGS_ENCRYPTION_KEY}`. Both must already be present on the Coolify app
with `is_literal=true`.

```bash
# Option A — REST API
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/applications/mk404cskowkgcow48g8s8okw/envs \
  | python3 -c "import sys, json; rows = json.load(sys.stdin); \
     print('\n'.join(f\"{r['key']}\tis_literal={r.get('is_literal')}\" for r in rows))"
# Expect both POSTGRES_PASSWORD and SETTINGS_ENCRYPTION_KEY to be listed.

# Option B — tinker (no token; run on the Pi)
ssh leo@rpi 'docker exec coolify php artisan tinker --execute="
\$app = \App\Models\Application::where(\"uuid\", \"mk404cskowkgcow48g8s8okw\")->first();
foreach (\$app->environment_variables as \$e) {
    echo \$e->key . \"\t is_literal=\" . (\$e->is_literal ? \"1\" : \"0\") . PHP_EOL;
}
"'
```

If either is missing, **stop and fix before continuing** — these env vars
should already be in place from #46. To set one (`is_literal=true` is
mandatory for any value containing `$`):

```bash
# Generate a strong password into a local shell var FIRST (not committed, not echoed in scrollback)
export NEW_PG_PASSWORD=$(openssl rand -base64 36 | tr -d '/+=' | head -c 40)

# Option A — REST API
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/applications/mk404cskowkgcow48g8s8okw/envs \
  -d "{\"key\":\"POSTGRES_PASSWORD\",\"value\":\"$NEW_PG_PASSWORD\",\"is_literal\":true,\"is_buildtime\":false,\"is_runtime\":true}"

unset NEW_PG_PASSWORD
```

### 0.3 Backup current SQLite + checksum + copy to vault

This is the most important step. Do not skip. **[CONFIRM]** — this stops the
running backend container so the SQLite file is consistent at copy time.

```bash
ssh leo@rpi '
set -euo pipefail
TS=$(date +%Y%m%d-%H%M)
mkdir -p /mnt/nvme/leo/backups /mnt/nvme/home/leo/vaults/brain/Health-Backups
docker stop $(docker ps -q --filter name=health-tracker-backend) || true
docker run --rm \
  -v health-tracker-data:/src:ro \
  -v /mnt/nvme/leo/backups:/dest \
  alpine \
  tar czf /dest/health.db.pre-postgres-${TS}.tar.gz -C /src .
sha256sum /mnt/nvme/leo/backups/health.db.pre-postgres-${TS}.tar.gz \
  | tee /mnt/nvme/leo/backups/health.db.pre-postgres-${TS}.sha256
cp /mnt/nvme/leo/backups/health.db.pre-postgres-${TS}.tar.gz \
   /mnt/nvme/leo/backups/health.db.pre-postgres-${TS}.sha256 \
   /mnt/nvme/home/leo/vaults/brain/Health-Backups/
ls -lh /mnt/nvme/leo/backups/health.db.pre-postgres-${TS}.*
ls -lh /mnt/nvme/home/leo/vaults/brain/Health-Backups/health.db.pre-postgres-${TS}.*
'
```

**Record the timestamp** (`echo $TS` value) — `RESTORE.md` needs it if you roll
back. Suggested: paste it into the cutover ticket.

The backend container will be restarted automatically by Coolify in step 4; no
need to start it manually now.

### 0.4 Tag the rollback point

```bash
git fetch origin
git tag pre-postgres-cutover origin/main
git push origin pre-postgres-cutover
```

This pins the pre-cutover code at the tip of `main` so `RESTORE.md` step 2
has a well-defined target.

---

## 1. Switch Coolify build_pack + docker_compose_location

Backend app must switch from `dockerfile` to `dockercompose`, and the compose
file path must be set to `/docker-compose.prod.yml` (default would be
`/docker-compose.yaml`). `instant_deploy=false` so we don't trigger a deploy
before the PR is merged.

### Option A — REST API (preferred)

```bash
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/applications/mk404cskowkgcow48g8s8okw \
  -d '{
    "build_pack": "dockercompose",
    "docker_compose_location": "/docker-compose.prod.yml",
    "base_directory": "/",
    "instant_deploy": false
  }'
```

### Option B — tinker (run on the Pi)

```bash
ssh leo@rpi 'docker exec coolify php artisan tinker --execute="
\$app = \App\Models\Application::where(\"uuid\", \"mk404cskowkgcow48g8s8okw\")->first();
\$app->build_pack = \"dockercompose\";
\$app->docker_compose_location = \"/docker-compose.prod.yml\";
\$app->base_directory = \"/\";
\$app->save();
echo \"build_pack=\" . \$app->build_pack . PHP_EOL;
echo \"docker_compose_location=\" . \$app->docker_compose_location . PHP_EOL;
"'
```

Verify the change took:

```bash
ssh leo@rpi 'docker exec coolify-db psql -U coolify -d coolify -c \
  "SELECT name, build_pack, docker_compose_location, base_directory \
   FROM applications WHERE uuid='\''mk404cskowkgcow48g8s8okw'\'';"'
```

---

## 2. Update DATABASE_URL (must be `is_literal=true`)

New value must be exactly:
`postgresql+asyncpg://health:${POSTGRES_PASSWORD}@postgres:5432/health`

`is_literal=true` is REQUIRED — the value contains a `$`, and without
`is_literal` Coolify will try to expand `${POSTGRES_PASSWORD}` at config-render
time instead of leaving it for Compose to resolve at container-start time.

### Option A — REST API

First, find the env var UUID:

```bash
ENV_UUID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/applications/mk404cskowkgcow48g8s8okw/envs \
  | python3 -c "import sys, json; print(next(r['uuid'] for r in json.load(sys.stdin) if r['key']=='DATABASE_URL'))")

curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/applications/mk404cskowkgcow48g8s8okw/envs \
  -d "{
    \"key\":\"DATABASE_URL\",
    \"value\":\"postgresql+asyncpg://health:\${POSTGRES_PASSWORD}@postgres:5432/health\",
    \"is_literal\":true,
    \"is_buildtime\":false,
    \"is_runtime\":true
  }"
```

(Coolify's env PATCH endpoint matches by key, not uuid, but ENV_UUID above is
useful for the DELETE-and-recreate fallback if PATCH refuses to flip
`is_literal`.)

### Option B — tinker

```bash
ssh leo@rpi 'docker exec coolify php artisan tinker --execute="
\$app = \App\Models\Application::where(\"uuid\", \"mk404cskowkgcow48g8s8okw\")->first();
\$app->environment_variables()
    ->where(\"key\", \"DATABASE_URL\")
    ->update([
        \"value\" => \"postgresql+asyncpg://health:\\\${POSTGRES_PASSWORD}@postgres:5432/health\",
        \"is_literal\" => true,
        \"is_runtime\" => true,
    ]);
foreach (\$app->environment_variables()->where(\"key\", \"DATABASE_URL\")->get() as \$row) {
    echo \"is_preview=\" . (\$row->is_preview ? \"1\" : \"0\") . \" value=\" . \$row->value . \" literal=\" . (\$row->is_literal ? \"1\" : \"0\") . PHP_EOL;
}
"'
```

**Note**: the polymorphic env-var table stores TWO rows per key
(`is_preview=false` for prod, `is_preview=true` for preview). The Eloquent
`->update()` above hits both. Confirm both rows print with `literal=1`.

---

## 3. Merge the PR

User action — merge the combined `feat/postgres-cutover` PR via the GitHub
UI. Coolify's manual webhook will pick up the push to `main` and queue a
deploy automatically.

If autodeploy is disabled or the webhook fails, trigger it manually in step 4.

---

## 4. Trigger Coolify deploy (only if step 3 didn't autotrigger)

Check first whether a deploy is already in-flight from the merge webhook:

```bash
ssh leo@rpi 'docker exec coolify-db psql -U coolify -d coolify -c \
  "SELECT status, LEFT(commit, 10) AS commit, created_at \
   FROM application_deployment_queues \
   WHERE application_id::text = ( \
     SELECT id::text FROM applications WHERE uuid='\''mk404cskowkgcow48g8s8okw'\'') \
   ORDER BY created_at DESC LIMIT 3;"'
```

If the top row is `in_progress` or `queued` for the merge commit, skip the
manual trigger and go to step 5. Otherwise:

### Option A — REST API

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/deploy?uuid=mk404cskowkgcow48g8s8okw"
```

### Option B — tinker

```bash
ssh leo@rpi 'docker exec coolify php artisan tinker --execute="
\$app = \App\Models\Application::where(\"uuid\", \"mk404cskowkgcow48g8s8okw\")->first();
\$uuid = new \Visus\Cuid2\Cuid2;
\$result = queue_application_deployment(application: \$app, deployment_uuid: \$uuid, force_rebuild: false, is_api: true);
echo \"deployment_uuid: \" . \$uuid . PHP_EOL;
echo \"status: \" . \$result[\"status\"] . PHP_EOL;
"'
```

---

## 5. Wait for postgres healthy + backend running

```bash
# Watch until postgres reports healthy (10s healthcheck interval, 30s start_period)
ssh leo@rpi 'until docker inspect --format="{{.State.Health.Status}}" health-tracker-postgres 2>/dev/null | grep -q healthy; do
  echo "$(date +%H:%M:%S) waiting for postgres..."
  sleep 5
done
echo "postgres healthy"
docker ps --filter name=health-tracker- --format "table {{.Names}}\t{{.Status}}"'
```

Then wait for backend:

```bash
ssh leo@rpi 'until docker ps --filter name=health-tracker-backend --format "{{.Status}}" | grep -q "Up "; do
  echo "$(date +%H:%M:%S) waiting for backend..."
  sleep 5
done
docker logs --tail 30 health-tracker-backend'
```

Backend will log SQLAlchemy init + Alembic running migrations. Expected end
state: uvicorn listening on `0.0.0.0:8000`, no tracebacks, postgres tables
created via `alembic upgrade head` (run by the entrypoint or the lifespan
hook). If you see `Connection refused` or `pysqlite is not async`, **stop and
roll back** — the env var change in step 2 didn't take effect.

---

## 6. Run the migration script in a one-shot container

The script needs to reach the `postgres` service on the Coolify-managed
network AND read the SQLite file from the `health-tracker-data` volume.

First, discover the network name (Coolify generates it from the project +
environment):

```bash
NETWORK=$(ssh leo@rpi 'docker inspect health-tracker-backend --format "{{range \$k,\$v := .NetworkSettings.Networks}}{{\$k}} {{end}}" | tr " " "\n" | grep -v "^$" | head -1')
echo "network=$NETWORK"

IMAGE=$(ssh leo@rpi 'docker inspect health-tracker-backend --format "{{.Config.Image}}"')
echo "image=$IMAGE"
```

Then run the migration. The script connects with the **sync** psycopg2 driver
(separate from the backend's asyncpg) — both can use the same DB credentials
because Postgres doesn't care which driver opens the connection.

**[CONFIRM]** — this is the write step against production Postgres.

```bash
ssh leo@rpi "
PG_PASSWORD=\$(docker exec health-tracker-postgres printenv POSTGRES_PASSWORD)
docker run --rm \\
  --network ${NETWORK} \\
  -v health-tracker-data:/sqlite-src:ro \\
  ${IMAGE} \\
  python -m scripts.migrate_sqlite_to_postgres \\
    --sqlite /sqlite-src/health.db \\
    --postgres postgresql+psycopg2://health:\${PG_PASSWORD}@postgres:5432/health \\
    --prune-expired-sessions
"
```

Expected output: per-table row counts, JSON deep-equal sample report, FK
orphan report (must be 0), and exit code 0. If the script exits non-zero,
**stop and roll back** — do not try to fix forward.

Re-run the same command to confirm idempotency — it must exit 1 with
"target already migrated, refusing".

---

## 7. Smoke checklist (qa-engineer step, run by Leo)

Run each check in order. Stop on the first failure and roll back.

- [ ] `curl -s -o /dev/null -w "%{http_code}\n" https://health.leo-figueiredo.com/api/v1/health` → `200`
- [ ] Open `https://health.leo-figueiredo.com` in browser, enter PIN, log in
- [ ] Past entries list renders (count matches: expect ~47 entries)
- [ ] Open the most recent entry — symptoms + photos load
- [ ] Open insights / feature-matrix → CSV export downloads
- [ ] CSV contains >900 weather rows
- [ ] Create a NEW entry (e.g. one symptom + one photo) → save
- [ ] `ssh leo@rpi 'docker restart health-tracker-backend'` → entry still present after restart
- [ ] Check today's vault file exists: `ssh leo@rpi 'ls -la /mnt/nvme/home/leo/vaults/brain/Daily/Health-Logs/$(date +%Y-%m-%d).md'`
- [ ] Labs page: open most recent lab — markers render
- [ ] `ssh leo@rpi 'docker exec health-tracker-postgres psql -U health -d health -c "SELECT COUNT(*) FROM entries;"'` → expected count

---

## 8. Post-cutover housekeeping (NEXT 2 WEEKS)

- **DO NOT delete** the `health-tracker-data` docker volume (still holds the live
  SQLite file as a passive backup).
- **DO NOT remove** the dated tarball from `/mnt/nvme/leo/backups/` or from
  `/mnt/nvme/home/leo/vaults/brain/Health-Backups/`.
- Daily-check the postgres-backup sidecar wrote a dump:
  `ssh leo@rpi 'ls -lh /mnt/nvme/home/leo/vaults/brain/Health-Backups/'`
- Watch for "missing entry" or "missing photo" issues. If any data-loss
  report comes in within 2 weeks, restore from the SQLite tarball
  (per RESTORE.md) to inspect.
- After 2 weeks of stability, file a follow-up issue to:
  1. `docker volume rm health-tracker-data`
  2. Move the old tarball to cold storage
  3. Drop this runbook from the active scripts/ directory (move to docs/)

---

## Rollback

If any of cutover steps 5–7 fail, follow
[migration_rollback/RESTORE.md](./migration_rollback/RESTORE.md). 5-min
recovery. Do not try to fix forward on a broken data migration.
