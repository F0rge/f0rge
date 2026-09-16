# Tenancy QA — Stockroom Option C

Isolation is proven in `uv run pytest` (`tests/test_tenancy_routing.py`, `tests/test_tenant_isolation.py`, `tests/test_tenant_background.py`, `tests/test_provisioning.py`, `tests/test_platform_signup.py`).

Live develop walkthrough is **blocked on #701** (human Railway/DNS/SMTP). Do not drop a QA Tenant database without Leonardo; suspend the row instead.

## Local (this PR)

1. Platform DB + bootstrap: `uv run alembic -c alembic_platform.ini upgrade head` then `python -m app.platform.bootstrap_default_tenant`.
2. API `:8003` with `X-Tenant-Host: localhost`. `GET /api/v1/health` has no header. `GET /api/v1/skus` without header → `404 tenant_not_found`.
3. Workspace `:3003` sends `X-Tenant-Host` from `window.location.hostname`. Login shows branding from `GET /api/v1/branding`.
4. Landing `:3004` → `/signup` → log-mode verify link → `/verify` polls until `ready` → **Open workspace** → `{slug}.localhost:3003/login` (not auto-session).
5. Cookie from Tenant A + `X-Tenant-Host` of Tenant B → `401`.

## Develop (after #701)

Replace hosts with `*.stockroom-dev.leo-figueiredo.com`. Record status codes and screenshots on the PR:

1. Landing create `qa-<date>` → check-email → verify → Open workspace → login form → empty Home.
2. Create one SKU on qa; search Vellano catalogue → absent.
3. Replay `vellano_session` on the qa host → 401; reverse → 401.
4. `nope.<base>` login → “No workspace at this address.”
5. Vellano golden path still works (login, catalogue, invoice PDF prefix `vellano`).
6. Same slug again → taken.
7. Suspend qa Tenant → host 404s. Leave the database; do not drop it.
