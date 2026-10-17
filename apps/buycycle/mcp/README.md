# Buycycle MCP

Read-only MCP server for the buycycle deal tracker. Streamable HTTP at `/mcp`.

It is reachable **only over Tailscale**, at `http://100.103.61.77:8097/mcp`. There is no public hostname and no Cloudflare tunnel. The bearer token stays required on every request.

## Run

```bash
export BUYCYCLE_MCP_TOKEN='replace-me'
export BUYCYCLE_DB=/data/buycycle.turso.db
uv run --project apps/buycycle/mcp python -m buycycle_mcp
```

The process listens on `0.0.0.0:8097` inside the container. On the Pi, publish that port on the tailnet address only: `100.103.61.77:8097:8097`.

It refuses to start when `BUYCYCLE_MCP_TOKEN` is unset or blank. Clients send `Authorization: Bearer <token>`. Anything else gets 401.

## Env

| Name | Required | Default |
| --- | --- | --- |
| `BUYCYCLE_MCP_TOKEN` | yes | none; startup exits if missing |
| `BUYCYCLE_DB` | no | `/data/buycycle.turso.db` in the image; locally the tracker default `tracker/buycycle.turso.db` |
| `BUYCYCLE_MCP_HOST` | no | `0.0.0.0` |
| `BUYCYCLE_MCP_PORT` | no | `8097` |

## Database mount

Use the same data volume as the dashboards, mounted **read-only** at `/data`. The database file is `/data/buycycle.turso.db` (the pyturso file the tracker writes). The server opens it with SQLite `mode=ro&immutable=1` and has no write path.

Coolify: persistent storage `buycycle-data` → `/data`, read only. Do not give this container its own copy of the database.

## Tools

Margins use the dashboard fee config in `tracker/fees.py` and are labelled `estimate`.

- `search_listings` — kind (`bike` or `wheels`), price min/max, days on market min/max, minimum price-drop percent, minimum net margin, brand, size, country. Sortable. Limit capped at 50.
- `get_listing` — one id, with details and the full price history.
- `todays_deals` — new listings and price drops for the current Europe/Luxembourg day, ranked by estimated net margin.
- `stats` — last run, counts, and data freshness.

## Deploy

Separate Coolify app, CI webhook only (`COOLIFY_WEBHOOK_BUYCYCLE_MCP`). The manifest `app_uuid` is a placeholder until that app exists, so deploys skip. Dockerfile: `apps/buycycle/mcp/Dockerfile`, build context `/`. No domain.
