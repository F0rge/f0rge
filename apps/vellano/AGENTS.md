# Vellano — Agent Instructions

Gauteng furniture retailer back office (stock, books, till). Sibling app next to Marrow and dk. **Never** nest this under `apps/marrow/`. **Never** a new repo.

Owner routing (even though `.cursor/rules/orchestration.mdc` still lists marrow paths):

| Area | Sub-agent |
|------|-----------|
| `apps/vellano/backend` | `fastapi-backend` |
| `apps/vellano/frontend` | `frontend-dev` |
| Nx / Docker / Railway / `.github/deploy` | `devops` |

Read `~/.cursor/agent-memory/<agent>/MEMORY.md` first. Write gotchas back when done.

## UI — IBM Carbon (explicit exception to `ui-kit.mdc`)

- **This app uses IBM Carbon (`@carbon/react`, `@carbon/styles`, `@carbon/icons-react`).**
- Do **not** import `@f0rge/ui`, `@f0rge/ui/forms`, or `@f0rge/ui/api`.
- Do **not** put Carbon in `libs/ui`. Do **not** run `add-ui-primitive` for Vellano.
- `ui-kit.mdc` remains the default for Marrow and dk. This nested AGENTS.md is the exception.
- Superdesign: try the Superdesign plugin first for frontend/UI. If the CLI reports credits/quota/paywall/auth failure, skip the canvas, implement Carbon, and record that in the PR. Do not invent extra retries.

## Stack

- Backend: FastAPI Python 3.10 + async SQLAlchemy + asyncpg + Alembic. API prefix `/api/v1`.
- Frontend: Next.js App Router `output: 'standalone'`.
- Auth cookie (S1, not S0): `vellano_session` — **not** `ht_session`.
- Import only: `f0rge_core`, `f0rge_db`, `f0rge_storage`, `f0rge_testing`. No Vellano domain in shared libs.

## Local ports (locked)

| Service | Port |
|---------|------|
| API | `:8003` |
| Frontend | `:3003` |
| Postgres | `:5433` |

Do not use Marrow `:8000/:3000` or dk `:8002/:3002`.

## Own database

```bash
cd apps/vellano && docker compose up -d postgres
```

`DATABASE_URL=postgresql+asyncpg://vellano:vellano@localhost:5433/vellano`

**Never** reuse Marrow `DATABASE_URL`, `ht-postgres`, Railway `pgvector`, Redis, or the photos bucket.

## Running

```bash
cd apps/vellano && docker compose up -d postgres
cd apps/vellano/backend && uv run uvicorn app.main:app --port 8003 --reload
cd apps/vellano/frontend && npm run dev   # :3003, rewrites /api/* → :8003
```

Signup/login is S1. S0 has `GET /api/v1/health` and a Carbon shell only.

## Railway

**Own Railway project** — not Marrow `zoological-fulfillment`, not the Marrow develop environment, not Marrow Postgres/Redis/photos.

This PR is **repo config only**. CoS / Leo provisions the Vellano Railway project and services separately. Do not add `vellano-*` services to the Marrow project.

- Config files: `apps/vellano/{backend,frontend}/railway.toml`
- No Root Directory. Config File = that `railway.toml`
- `watchPatterns` = `apps/vellano/**` + libs actually imported
- Manifest: `branches: [develop]` only. No production, no `main`, no custom DNS in S0
- CoS patches `railway.health_url.develop` after the Vellano project exists

## Non-goals

The app does not send email, pay, file VAT, or open a bank account. Do not implement S1–S11 product features here (auth, SKUs, ledger, till).

## Python

`uv --project apps/vellano/backend`. **Never** create a root `uv.lock`. Python 3.10 only (`from __future__ import annotations`; no `X | Y`).

## PRs

Target `develop` only. Do not merge to `main` from this epic.
