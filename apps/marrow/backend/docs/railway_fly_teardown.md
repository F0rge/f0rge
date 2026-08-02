# Fly teardown (post Railway cutover)

Do **not** run destroy steps until **48h after custom-domain DNS is green** on Railway.

## Already done at cutover

- Fly `marrow` / `marrow-dev` web+worker scaled to **0** during dump freeze (kept for rollback).
- Railway holds prod+develop data + photos.
- CI no longer deploys to Fly (`fly-deploy-reusable.yml` removed).

## After 48h green (Leo OK)

1. Confirm dig/curl on `api.marrow-health.com` / `app-dev…` hit Railway (not Fly IPs).
2. Destroy Fly apps: `marrow`, `marrow-dev`, `marrow-mcp`, `marrow-mcp-dev`, `marrow-ui`, `marrow-ui-dev`.
3. Detach/retire MPG `f0rge-db` when unused; retire Upstash Redis + Tigris buckets.
4. Delete GitHub secret `FLY_API_TOKEN`.
5. Follow-up PR: delete `apps/marrow/**/fly*.toml`.

## Rollback (within 48h)

1. Cloudflare DNS: restore previous Fly A/CNAME targets.
2. `fly scale count web=1 worker=1 -a marrow` (and marrow-dev).
