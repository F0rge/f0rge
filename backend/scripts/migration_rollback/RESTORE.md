# Rollback — Postgres cutover failure

If any cutover step fails, follow this in order. Target wall-clock: **~5 min**
from trigger to verified `/api/v1/health` 200.

Coolify backend app UUID: `mk404cskowkgcow48g8s8okw`.

`$TS` is the timestamp recorded in `cutover.md` step 0.3 (format:
`YYYYMMDD-HHMM`). Set it once at the top of your shell:

```bash
export TS=20260516-1830   # replace with the value you recorded
```

---

## Trigger criteria (ANY of)

- `/api/v1/health` non-200 for >5 min after cutover.md step 5 reports backend up
- Row-count mismatch reported by `migrate_sqlite_to_postgres.py`
- Any router returns 5xx during the smoke sweep (cutover.md §7)
- Any item in the smoke checklist (cutover.md §7) fails
- `pysqlite is not async` / SQLAlchemy driver errors in backend logs
- Postgres container in continuous restart loop (not just slow startup)

---

## Recovery steps

### 1. Stop the new containers

```bash
ssh leo@rpi '
docker stop health-tracker-backend health-tracker-frontend \
            health-tracker-postgres health-tracker-postgres-backup 2>/dev/null || true
docker ps --filter name=health-tracker- --format "table {{.Names}}\t{{.Status}}"
'
```

Expect: no rows, or only Exited rows.

### 2. Roll back the code to the pre-cutover tag

If the PR has NOT yet been merged: nothing to revert in git. Skip to step 3.

If the PR HAS been merged:

```bash
# Option A — revert the merge commit (preferred — preserves history)
git fetch origin
git checkout main
git revert -m 1 $(git log --merges -n 1 --pretty=%H origin/main)
git push origin main

# Option B — force-with-lease back to the tag (use only if Option A is messy)
# This rewrites main; coordinate with anyone else who fetched the merge.
git push origin pre-postgres-cutover:main --force-with-lease
```

Coolify will pick up the new tip of `main` on its next webhook delivery.

### 3. Flip Coolify back to dockerfile build pack

Backend must be back on `build_pack=dockerfile` before the next deploy, or
Coolify will try to bring postgres up again from the reverted compose file
(which won't include it).

```bash
# Option A — REST API
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/applications/mk404cskowkgcow48g8s8okw \
  -d '{
    "build_pack": "dockerfile",
    "dockerfile_location": "/Dockerfile",
    "base_directory": "/backend",
    "instant_deploy": false
  }'

# Option B — tinker
ssh leo@rpi 'docker exec coolify php artisan tinker --execute="
\$app = \App\Models\Application::where(\"uuid\", \"mk404cskowkgcow48g8s8okw\")->first();
\$app->build_pack = \"dockerfile\";
\$app->dockerfile_location = \"/Dockerfile\";
\$app->base_directory = \"/backend\";
\$app->save();
echo \"build_pack=\" . \$app->build_pack . PHP_EOL;
"'
```

### 4. Reset DATABASE_URL to the SQLite value

```bash
# Option A — REST API
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/applications/mk404cskowkgcow48g8s8okw/envs \
  -d '{
    "key":"DATABASE_URL",
    "value":"sqlite+aiosqlite:///data/health.db",
    "is_literal":false,
    "is_buildtime":false,
    "is_runtime":true
  }'

# Option B — tinker
ssh leo@rpi 'docker exec coolify php artisan tinker --execute="
\$app = \App\Models\Application::where(\"uuid\", \"mk404cskowkgcow48g8s8okw\")->first();
\$app->environment_variables()
    ->where(\"key\", \"DATABASE_URL\")
    ->update([
        \"value\" => \"sqlite+aiosqlite:///data/health.db\",
        \"is_literal\" => false,
        \"is_runtime\" => true,
    ]);
"'
```

Note: the reverted code on `main` is the pre-#46 SYNCHRONOUS sqlite code, so
the URL must be the SYNC form `sqlite:///data/health.db`, NOT
`sqlite+aiosqlite:///data/health.db`. If `pre-postgres-cutover` was tagged
AFTER #46 merged (i.e. the rolled-back code is still async), use
`sqlite+aiosqlite:///data/health.db`. Verify by looking at
`backend/app/core/database.py` at the tagged commit before deciding.

### 5. Restore SQLite from the backup tarball

This overwrites the contents of the `health-tracker-data` docker volume with
the pre-cutover snapshot. The volume itself is preserved; only its contents
are replaced.

```bash
ssh leo@rpi "
set -euo pipefail
test -f /mnt/nvme/leo/backups/health.db.pre-postgres-${TS}.tar.gz \
  || { echo 'BACKUP NOT FOUND for TS=${TS}'; exit 1; }
sha256sum -c /mnt/nvme/leo/backups/health.db.pre-postgres-${TS}.sha256
docker run --rm \
  -v health-tracker-data:/dest \
  -v /mnt/nvme/leo/backups:/src:ro \
  alpine \
  sh -c 'rm -rf /dest/* /dest/.[!.]* 2>/dev/null; tar xzf /src/health.db.pre-postgres-${TS}.tar.gz -C /dest'
docker run --rm -v health-tracker-data:/data alpine ls -lh /data/health.db
"
```

The final `ls -lh` should report a file roughly 929 KB (matches what was
captured in `project_health_tracker_postgres_deploy_2026-05-16.md`).

### 6. Trigger a redeploy

```bash
# Option A — REST API
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/deploy?uuid=mk404cskowkgcow48g8s8okw"

# Option B — tinker
ssh leo@rpi 'docker exec coolify php artisan tinker --execute="
\$app = \App\Models\Application::where(\"uuid\", \"mk404cskowkgcow48g8s8okw\")->first();
\$uuid = new \Visus\Cuid2\Cuid2;
queue_application_deployment(application: \$app, deployment_uuid: \$uuid, force_rebuild: true, is_api: true);
echo \"deployment_uuid: \" . \$uuid . PHP_EOL;
"'
```

`force_rebuild: true` is intentional — the Dockerfile build image may be stale
or evicted.

Wait for the backend container to come up:

```bash
ssh leo@rpi 'until docker ps --filter name=health-tracker-backend --format "{{.Status}}" | grep -q "Up "; do
  echo "$(date +%H:%M:%S) waiting for backend..."
  sleep 5
done
docker logs --tail 30 health-tracker-backend'
```

### 7. Verify

```bash
# Liveness
curl -s -o /dev/null -w "%{http_code}\n" https://health.leo-figueiredo.com/api/v1/health
# Expect: 200

# Spot check — past entries list (requires auth cookie; do this in browser)
# Open https://health.leo-figueiredo.com, log in with PIN, confirm past
# entries render exactly as they did before cutover.

# Confirm SQLite file modtime matches the backup snapshot (no surprise writes)
ssh leo@rpi 'docker run --rm -v health-tracker-data:/data alpine ls -la /data/health.db'
```

### 8. Post-rollback cleanup (optional — only after smoke is green)

- Leave the postgres volume in place. Do NOT `docker volume rm
  health-postgres-data` until you've taken a pg_dump for forensics:

```bash
ssh leo@rpi "
docker run --rm \
  -v health-postgres-data:/var/lib/postgresql/data \
  -v /mnt/nvme/leo/backups:/dump \
  pgvector/pgvector:pg16 \
  sh -c 'pg_ctl -D /var/lib/postgresql/data -l /tmp/pg.log start && \
         pg_dump -U health -Fc health > /dump/health-postgres-failed-${TS}.dump && \
         pg_ctl -D /var/lib/postgresql/data stop'
"
```

(The dump is for diagnosing what went wrong with the migration — keep it
until the root cause is understood.)

---

## Do NOT

- Try to fix forward on a broken data migration. Roll back first, diagnose
  from logs + the postgres dump, then re-run cutover with a fixed script.
- Delete `health-postgres-data` volume before taking a pg_dump.
- Modify code or env vars in flight to "patch" the failure — roll back to a
  known-good state, then iterate.
- Skip the sha256 verification in step 5 — silent backup corruption is the
  worst-case scenario and the checksum is the only guard.
- Run the migration script a second time against a partially-migrated
  Postgres — the idempotency guard refuses, by design.
