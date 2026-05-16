# MCP Server — secure external access to the health DB

## Why this exists

Claude Code and Claude Desktop both need a way to query my health data conversationally — surface recent lab trends, pull symptom history, cross-reference treatments. Handing out the raw Postgres credentials of the `health` superuser is unsafe (writes, secret tables, etc.). The Model Context Protocol (MCP) is the standard wire format for exposing tools to Claude, and an MCP server lets us put three independent layers of security in front of the database without having to invent a custom auth scheme.

## Three-layer security model

1. **Network edge (remote only)** — Cloudflare Access fronts `health-mcp.leo-figueiredo.com`. Only authenticated identities (Leo's Google account via the existing Zero Trust policy) can reach the container. The tunnel terminates at `cloudflared` on the Pi; nothing else on the public internet can talk to port 8005/8007.
2. **Application auth** — a Bearer token, generated in `/settings`, stored Fernet-encrypted at rest in `user_settings.mcp_bearer_token_encrypted`, must be presented on every `/mcp/*` HTTP call. Token rotation is one click in the UI; the old hash is immediately invalidated.
3. **Database privilege** — the MCP server connects as the `healthtracker_ro` role created in migration `004`. That role has `CONNECT` on `health`, `USAGE` on `public`, and `SELECT` on every existing/future table in `public`. No `INSERT`, `UPDATE`, `DELETE`, or `DDL`. Any attempt to mutate fails at the Postgres permission layer regardless of bugs in app code.

Layers 2 and 3 apply to both transports (stdio and streamable-http). Layer 1 only applies to remote use over HTTPS — local `docker exec` over stdio bypasses Cloudflare because it never touches the public internet.

## Architecture

```
Claude Code (Mac)                                      Claude Desktop (remote)
        |                                                       |
        | ssh leo@rpi                                           | https://health-mcp.leo-figueiredo.com
        v                                                       v
   docker exec -i                                       Cloudflare Access (JWT)
   health-tracker-mcp                                          |
   (stdio transport)                                           v
        |                                              cloudflared tunnel
        |                                              (homelab-services)
        |                                                      |
        |                                                      v
        |                                              localhost:8007 (host)
        |                                                  -> :8005 (container)
        |                                                      |
        |                                                      v
        |                                              streamable-http transport
        |                                              + Bearer token check
        |                                                      |
        +--------------------> mcp-server (app.mcp) <----------+
                                       |
                                       | asyncpg as healthtracker_ro (SELECT only)
                                       v
                               health-tracker-postgres
```

## Deployment runbook

1. **Generate and set `HEALTHTRACKER_RO_PASSWORD`** in the Coolify env for the health-tracker stack:
   ```bash
   openssl rand -hex 32
   ```
   Paste the value into Coolify under the application's environment variables. Mark it secret. The same value goes into the project `.env` file (Coolify writes it through to the container).

2. **Apply migrations** `004` and `005` — they create the `healthtracker_ro` role, grant SELECT on all existing tables, install the `embedding_queue` table, and install the AFTER triggers on the embedable source tables.
   ```bash
   docker exec health-tracker-backend uv run alembic upgrade head
   ```

3. **Deploy via Coolify** — the existing webhook on the GitHub repo redeploys the stack. The new `mcp-server` and `embedding-worker` services come up alongside `backend` and `postgres`.

4. **Verify locally on the Pi**:
   ```bash
   ssh leo@rpi 'curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8007/mcp/health'
   ```
   (Token comes from the `/settings` page after first login.)

5. **Verify Cloudflare** — see "Cloudflare setup" below.

## Cloudflare setup

**State at time of writing (verified 2026-05-16):**

- `cloudflared` is running on the Pi as a systemd unit (`cloudflared.service`, active since 2026-05-14), using `/etc/cloudflared/config.yml` and tunnel ID `6c58d6b1-ad4d-4df9-8249-0e2bb88a9c01` (`homelab-services`).
- `health.leo-figueiredo.com` is already routed through this tunnel to `localhost:3004` (frontend).
- **`health-mcp.leo-figueiredo.com` is NOT yet configured.** It's not in either `/etc/cloudflared/config.yml` or `/home/leo/.cloudflared/config.yml`, and DNS does not resolve.
- No `CLOUDFLARE_API_TOKEN` is available in this environment, so the steps below are **manual** and must be performed by the user.

**Manual setup steps:**

1. **Add an ingress rule on the Pi.** Edit `/etc/cloudflared/config.yml` (and `/home/leo/.cloudflared/config.yml` if you want to keep them in sync — currently they are identical), adding this block **before any catch-all `service: http_status:404` line**:
   ```yaml
   # Health Tracker MCP server (read-only DB access for Claude)
   - hostname: health-mcp.leo-figueiredo.com
     service: http://localhost:8007
   ```
   The port is **8007**, not 8005, because 8005 is already in use on the Pi by another project (Entre Nos backend). The `docker-compose.prod.yml` for health-tracker maps host `8007 -> container 8005`.

2. **Route DNS to the tunnel:**
   ```bash
   ssh leo@rpi 'cloudflared tunnel route dns 6c58d6b1-ad4d-4df9-8249-0e2bb88a9c01 health-mcp.leo-figueiredo.com'
   ```

3. **Reload cloudflared:**
   ```bash
   ssh leo@rpi 'sudo systemctl restart cloudflared'
   ```

4. **Add a Cloudflare Access policy.** In the Zero Trust dashboard (https://one.dash.cloudflare.com/), under **Access > Applications**:
   - Click **Add an application > Self-hosted**.
   - Name: `Health Tracker MCP`. Domain: `health-mcp.leo-figueiredo.com`.
   - Session duration: 24 hours (or whatever matches the other Pi-hosted Access apps).
   - Policy: `Allow` if `Emails == leo.defig@gmail.com`. Identity provider: Google (already configured in Zero Trust).
   - Optionally enable **Service Auth** with a service token if you want headless clients (e.g. an automation runner) to call the endpoint without an interactive Google login. For Claude Desktop, browser-based auth is fine.

5. **Verify** end-to-end:
   ```bash
   curl -fsS https://health-mcp.leo-figueiredo.com/mcp/health
   ```
   The first call from a fresh browser should redirect to the Cloudflare Access login. Subsequent calls with a valid `CF_Authorization` cookie should reach the container.

## Local stdio wrapper for Claude Code

For local use on the Mac, Claude Code talks to the container over stdio via `ssh + docker exec` — no network exposure required.

Template lives at `scripts/mcp-stdio-wrapper.sh.template`. Install:

```bash
cp scripts/mcp-stdio-wrapper.sh.template ~/.local/bin/mcp-stdio-wrapper.sh
chmod +x ~/.local/bin/mcp-stdio-wrapper.sh
# Edit the SSH host inside the script if your alias is not `leo@rpi`.

claude mcp add health-tracker --transport stdio -- ~/.local/bin/mcp-stdio-wrapper.sh
```

Verify with `claude mcp list` (the new server should appear) and then within a `claude` session by invoking one of its tools.

## Adding a new tool

1. Add a new function in `backend/app/mcp/tools.py`.
2. Decorate it with `@server.tool()` from the MCP SDK and write a docstring — the docstring is the tool description Claude sees.
3. Use the read-only engine factory `get_ro_engine()` for every DB call. Do not pull in a write-capable session.
4. Add a test in `backend/tests/test_mcp_tools.py` that exercises the tool against a populated test DB.
5. Restart `mcp-server` (`docker compose restart mcp-server`) — tool discovery happens at startup.

## Troubleshooting

- **`401` from `/mcp/*`** — Bearer token is missing, wrong, or has been rotated. Regenerate in `/settings`, update the client config (`claude mcp add ...` or the Desktop JSON), and retry.
- **HTML challenge page or redirect to `cloudflareaccess.com`** — the Cloudflare Access cookie has expired or is missing. Open `https://health-mcp.leo-figueiredo.com/` in a browser, authenticate, then re-issue the call (the browser sets `CF_Authorization`).
- **`permission denied for table X`** — expected behaviour for any DML statement issued via the read-only role. The fix is not to grant DML; the fix is to wire the operation through the regular backend API which uses the read-write role.
- **`role "healthtracker_ro" does not exist`** — migration `004` was not applied. Run `alembic upgrade head` inside `health-tracker-backend`.
- **`connection refused` from cloudflared logs** — `mcp-server` container isn't up, or it's bound to a different port than the ingress rule expects. Check `docker compose ps` and the `ports:` line in `docker-compose.prod.yml`.
- **stdio wrapper exits immediately** — usually means the SSH alias is wrong, the container name is wrong (it's `health-tracker-mcp`, not `health-tracker-mcp-server`), or `docker exec` can't allocate a TTY because `-i` was dropped. The template uses `-i` only — no `-t`.
