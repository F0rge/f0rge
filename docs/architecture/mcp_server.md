# MCP Server — secure external access to the health DB

## Why this exists

Claude Code and Claude Desktop need a way to query health data conversationally — surface recent lab trends, pull symptom history, cross-reference treatments. Handing out raw Postgres credentials is unsafe. The Model Context Protocol (MCP) exposes tools to Claude with layered security.

## Security model

1. **Application auth** — Bearer token from `/settings`, Fernet-encrypted at rest in `user_settings.mcp_bearer_token_encrypted`. Required on every `/mcp/*` call. Rotation invalidates the old hash immediately.
2. **Database privilege** — MCP connects as `healthtracker_ro` (migration `004`): `SELECT` only on `public` tables. No DML or DDL.

On Fly, the MCP app is public HTTPS (`marrow-mcp.fly.dev` / `marrow-mcp-dev.fly.dev`). Bearer token is the primary gate (no Cloudflare Access layer).

## Architecture

```
Claude Code / Claude Desktop
        |
        | https://marrow-mcp.fly.dev/mcp (prod)
        | https://marrow-mcp-dev.fly.dev/mcp (dev)
        v
streamable-http transport + Bearer token check
        |
        v
mcp-server (app.mcp) on Fly
        |
        | asyncpg as healthtracker_ro (SELECT only)
        v
Fly MPG (marrow / marrow_dev database)
```

## Fly deployment

| Env | Fly app | URL |
|---|---|---|
| Prod | `marrow-mcp` | https://marrow-mcp.fly.dev/mcp |
| Dev | `marrow-mcp-dev` | https://marrow-mcp-dev.fly.dev/mcp |

Deploy: `backend/fly.mcp.toml` (dev) / `fly.mcp.prod.toml` (prod). Secrets: `MCP_READONLY_DATABASE_URL` + `DATABASE_URL` (reader URLs from `fly mpg attach`).

Settings UI snippet uses `https://marrow-mcp.fly.dev/mcp` as the default remote URL.

## Local access from Claude Code

```bash
claude mcp add --transport http marrow https://marrow-mcp.fly.dev/mcp \
  --header "Authorization: Bearer <token from /settings>"
```

For dev: substitute `marrow-mcp-dev.fly.dev`.

## Adding a new tool

1. Add a function in `backend/app/mcp/tools.py` with `@server.tool()` and a docstring.
2. Use `get_ro_engine()` for every DB call.
3. Add a test in `backend/tests/test_mcp_tools.py`.
4. Redeploy MCP app on Fly.

## Troubleshooting

- **`401` from `/mcp/*`** — Bearer token missing, wrong, or rotated. Regenerate in `/settings`.
- **`permission denied for table X`** — expected for DML via read-only role; use the main API for writes.
- **`role "healthtracker_ro" does not exist`** — migration `004` not applied; check API `release_command` / alembic on Fly.
