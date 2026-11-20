> Canonical decisions: [`docs/adr/README.md`](../../../docs/adr/README.md). Follow [P-005](../../../docs/adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../../../docs/adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

# dk tag printer — Agent Instructions

DasKasas price tag tool. App `dk`, Host: the Pi (Coolify), prod only.
Resolve primary and reviewers with `node scripts/agents/agents.mjs route <repo-relative-path...>` from the repo root. Follow the [shared protocol](../../../docs/agents/protocol.md): `f0rge-delivery` covers build/CI work and `f0rge-devops` covers runtime operations, subject to the exact manifest route.

## Local dev

```bash
cd apps/dk/tag-printer && docker compose up --build
# Frontend http://localhost:3002, Backend http://localhost:8002
```

Or separately:

```bash
cd apps/dk/tag-printer/backend && uv run uvicorn app.main:app --port 8002 --reload
cd apps/dk/tag-printer/frontend && npm run dev -- --port 3002
```

## Production (Coolify on Pi)

| Coolify application (= Nx project) | Port | Domain |
|-----|------|--------|
| `dk-tag-printer-frontend` | 3002:3000 | https://tags.leo-figueiredo.com |
| `dk-tag-printer-backend` | 8002:8000 | https://tags-api.leo-figueiredo.com |

- Both are Coolify "Docker image" applications. CI builds the ARM64 Artifacts; Coolify pulls them.
- Build context: **repo root**; Dockerfiles under `apps/dk/tag-printer/{backend,frontend}/`
- cloudflared: `tags.` → localhost:3002, `tags-api.` → localhost:8002

## Critical gotchas

1. **`NEXT_PUBLIC_API_URL` is build-time** — it is baked into the frontend
   Artifact by `build.args` in the deploy block. Value: `https://tags-api.leo-figueiredo.com`
2. **Backend CORS** — runtime env `CORS_ORIGINS=https://tags.leo-figueiredo.com`
3. **Pi OOM** — frontend Dockerfile sets `NODE_OPTIONS=--max-old-space-size=1536`
4. **CF WAF** — synthetic smoke tests need a browser User-Agent on POST
   `/api/generate-pdf`; GET `/health` is fine with curl

## Release

A reviewed merge to `main` that affects either Project releases both, from one commit, through [the pipeline](../../../.github/deploy/README.md). Both services restart during a Release; a failed Release puts each service back on the image it ran before.

## Frontend kit

- Consume `@f0rge/ui` for primitives and chrome; labeled fields from `@f0rge/ui/forms`
- No local `cn` helper or copied `Button` — import from the kit
- **Tailwind 4** — `globals.css` `@source` must scan `libs/ui`
- Frontend Dockerfile must `COPY libs/ui` (same pattern as marrow) — build context is repo root
- Do **not** use `@f0rge/ui/api` — keep axios + `getApiBase()` for this stateless app
- Full import/token contract: `docs/agents/rules/ui-kit.md`

## Branches

Use the `main`-only workflow. A remote `develop` ref may still exist; it is read-only inventory here, not an approved long-lived branch. Do not open pull requests against it, and do not delete the ref or its ruleset from this file. Branch off `main`. A merge releases; Leo's review is the gate. See root [`AGENTS.md`](../../../AGENTS.md#git-flow-trunk-based-main-only).
