> Canonical decisions: [`docs/adr/README.md`](../../../docs/adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

# dk tag printer — Agent Instructions

DasKasas price tag tool. Deploy target: **Coolify on Pi** (prod only).
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

| App | UUID | Port | Domain |
|-----|------|------|--------|
| daskasas-frontend | `f080ossg88ows8k8csw40c4s` | 3002:3000 | https://tags.leo-figueiredo.com |
| daskasas-backend | `pskswsc8c0044ggo40go4og0` | 8002:8000 | https://tags-api.leo-figueiredo.com |

- Repo: `F0rge/f0rge`, branch `main`
- Build context: **repo root**; Dockerfiles under `apps/dk/tag-printer/{backend,frontend}/`
- cloudflared: `tags.` → localhost:3002, `tags-api.` → localhost:8002

## Critical gotchas

1. **`NEXT_PUBLIC_API_URL` is build-time** — Coolify must pass it as build-arg
   (`is_buildtime=true`). Value: `https://tags-api.leo-figueiredo.com`
2. **Backend CORS** — runtime env `CORS_ORIGINS=https://tags.leo-figueiredo.com`
3. **Pi OOM** — frontend Dockerfile sets `NODE_OPTIONS=--max-old-space-size=1536`
4. **CF WAF** — synthetic smoke tests need a browser User-Agent on POST
   `/api/generate-pdf`; GET `/health` is fine with curl

## Release hold

The existing **Deploy** workflow is disabled. In the proposed workflows, `deploy.yml` only reports preparation and `deploy-reusable.yml` fails under a release hold; neither calls Coolify or runs production smoke. The configured GitHub `production` environment does not protect direct Coolify operations. Runtime provider state has not been checked for this change.

The manifest and webhook names `COOLIFY_WEBHOOK_DASKASAS_BACKEND` / `COOLIFY_WEBHOOK_DASKASAS_FRONTEND` describe the historical source-building path; `watch_paths` selected affected apps there. Preserve these as inventory, not a route around the hold. Before authorized release work, read [the remaining artifact, secret migration and independent approval requirements](../../../.github/deploy/README.md), verify current provider state and obtain Leo's explicit release approval. A merge is not that approval.

## Frontend kit

- Consume `@f0rge/ui` for primitives and chrome; labeled fields from `@f0rge/ui/forms`
- No local `cn` helper or copied `Button` — import from the kit
- **Tailwind 4** — `globals.css` `@source` must scan `libs/ui`
- Frontend Dockerfile must `COPY libs/ui` (same pattern as marrow) — build context is repo root
- Do **not** use `@f0rge/ui/api` — keep axios + `getApiBase()` for this stateless app
- Full import/token contract: `docs/agents/rules/ui-kit.md`

## Branches

Use the `main`-only workflow. A remote `develop` ref may still exist; it is read-only inventory here, not an approved long-lived branch. Do not open pull requests against it, and do not delete the ref or its ruleset from this file. Branch off `main`. Do not merge or deploy without Leo's release approval. See root [`AGENTS.md`](../../../AGENTS.md#git-flow-trunk-based-main-only).
