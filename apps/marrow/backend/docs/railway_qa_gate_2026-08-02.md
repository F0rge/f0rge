# Railway cutover QA Gate — 2026-08-02

## Verdict

**PASS** — custom domains on Railway (prod + develop).

## Custom-domain evidence

| Check | Result |
|-------|--------|
| `api.marrow-health.com/api/v1/health` | 200 `{"status":"ok"}` (`server: railway-hikari`) |
| `api-dev.marrow-health.com/api/v1/health` | 200 `{"status":"ok"}` |
| `marrow-health.com/` / `www` / `app-dev` | 200 HTML |
| `mcp.marrow-health.com/mcp` / `mcp-dev` | 401 auth required (non-5xx) |
| TLS | `CN=api.marrow-health.com` (Let's Encrypt via Railway) |
| DNS | CNAMEs → `*.up.railway.app` (DoH); not Fly IPs |
| Photos | Bucket sync 287/56; MCP `list_photos_for_entry` 2026-04-01 → photo id 1; `/photos/1/file` → 401 unauth |
| DB | Prod 7/148/284; Develop 133/59/54; alembic `048` |

## CI

PR #438 merged to `develop` (Railway smoke, Fly deploy workflow removed).

## Fly

Web/worker at 0. Destroy after 48h per `railway_fly_teardown.md`.
