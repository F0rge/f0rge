# Railway cutover QA Gate — 2026-08-02

## Verdict

**PARTIAL PASS** — Railway prod + develop data/photos/services healthy on `*.up.railway.app`. Custom-domain DNS still on Fly (Cloudflare API token invalid; UI apply pending). Re-run domain section after DNS cutover.

## Evidence (Railway hosts)

| Check | Prod | Develop |
|-------|------|---------|
| API `/api/v1/health` | 200 `{"status":"ok"}` | 200 `{"status":"ok"}` |
| Frontend `/` | 200 | 200 |
| MCP `/mcp` | 401 (auth expected) | 401 |
| DB restore counts | users=7 entries=148 photos=284 alembic=048 | users=133 entries=59 photos=54 alembic=048 |
| Photo bucket sync | 287/287 objects; HEAD sample OK | 56/56 objects |

## Pending (custom domains)

Apply [`railway_dns_cutover_checklist.md`](railway_dns_cutover_checklist.md) in Cloudflare UI (DNS-only until cert ACTIVE), then:

- dig → Railway CNAME targets
- curl health/login/photo/MCP on `*.marrow-health.com` / `*-dev.*`
- Update this report to **PASS**

## Fly

Web/worker scaled to 0. Teardown after 48h: [`railway_fly_teardown.md`](railway_fly_teardown.md).
