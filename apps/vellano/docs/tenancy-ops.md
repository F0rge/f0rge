# Tenancy ops — Stockroom Option C (develop)

Live Railway / DNS / SMTP is **human-only** (#701). This runbook is the in-repo checklist. Do not put passwords or database URLs in git or PR text.

## Hosts (develop, after #701)

| Surface | URL |
| --- | --- |
| Landing | `https://stockroom-dev.leo-figueiredo.com` |
| API | `https://api.stockroom-dev.leo-figueiredo.com` |
| Workspaces | `https://*.stockroom-dev.leo-figueiredo.com` |
| Vellano (Company 1) | `https://vellano-dev.leo-figueiredo.com` + `https://vellano-dev-api.leo-figueiredo.com` |

Cloudflare: wildcard DNS **grey-cloud** (DNS-only) so Railway can issue the nested wildcard ACME cert. Keep existing `vellano-dev*` hosts.

Railway project **Vellano** `c76d8df1-d839-454c-a94a-79b930deaf38`, env **develop**. Never Marrow `zoological-fulfillment`.

## First-deploy order

1. Create database `vellano_platform` and roles `platform_app` + `tenant_admin` (`CREATEDB CREATEROLE`) on the **existing** Vellano Postgres instance. Do not create a second plugin. Do not point `PLATFORM_DATABASE_URL` at the Vellano Tenant database.
2. Set variables on `vellano-api` (JSON lists, not bare strings):
   - `PLATFORM_DATABASE_URL`, `PLATFORM_ADMIN_DATABASE_URL`
   - `TENANT_BASE_DOMAIN=stockroom-dev.leo-figueiredo.com`
   - `DEFAULT_TENANT_SLUG=vellano`
   - `DEFAULT_TENANT_HOSTNAMES=["vellano-dev.leo-figueiredo.com"]`
   - `LANDING_BASE_URL=https://stockroom-dev.leo-figueiredo.com`
   - `PLATFORM_SIGNUP_MODE=instant`
   - `PLATFORM_MAIL_MODE=smtp` and `PLATFORM_SMTP_*`
   - `SEED_DEV_EXTRAS=false` after bootstrap
3. One-time bootstrap (from a machine that can reach the platform DB):

   ```bash
   cd apps/vellano/backend
   uv run python -m app.platform.bootstrap_default_tenant
   ```

   Railway equivalent: `railway run --service vellano-api -e develop -- uv run python -m app.platform.bootstrap_default_tenant`
4. Flip `preDeployCommand` (already in `apps/vellano/backend/railway.toml`): `uv run python -m app.platform.migrate_all`. If `PLATFORM_DATABASE_URL` is unset, that command upgrades `DATABASE_URL` only so a merge before this checklist does not fail preDeploy.
5. Create the Landing service from `apps/vellano/landing/railway.toml`. Build-arg `API_URL` is the **internal** API URL. `NEXT_PUBLIC_TENANT_BASE_DOMAIN=stockroom-dev.leo-figueiredo.com`.

## migrate-all

```bash
cd apps/vellano/backend
uv run python -m app.platform.migrate_all
uv run python -m app.platform.migrate_all --only vellano
```

Exit non-zero if the platform chain or any `ready`/`provisioning` Tenant fails. Inspect failed signups in the platform `signups` table (`status=failed`, `failure_reason` — no secrets). Resume with `ProvisioningService.provision(signup_id)` or `python -m app.platform.provision`.

## Suspend

Set Tenant `status=suspended`. Hostname resolution only returns `ready`, so the Workspace 404s with `tenant_not_found`. Unsuspend by setting `ready` again. Do **not** drop the Tenant database without Leonardo.

## Backups

`pg_dump` **per database** (platform + each `tenant_<slug>`). The registry row holds the encrypted URL; rotate instance later by updating that row.

## Cookie

`vellano_session` and `vellano_customer_session` stay host-only. Never set `Domain=`.
