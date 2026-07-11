# Health Tracker (Marrow)

**Extends `~/.claude/CLAUDE.md`** — see there for global preferences, stack defaults, git workflow, boundaries, sub-agent delegation rules, family disambiguations, self-update protocol, and Brain vault encouragement. This file holds only project-specific rules.

Personal daily symptom check-in app for Leo's health research vault.

## Stack

- Backend: FastAPI + async SQLAlchemy + Postgres (asyncpg) — Python 3.10
- Frontend: Next.js 16 + React 19 + Tailwind 4 + shadcn/ui
- Auth: JWT in `ht_session` httpOnly cookie (email + password)
- Deploy: Fly.io (API, MCP, frontend) + Fly MPG Postgres + Tigris object storage

## Environments

### Production (`main`)

| Component | Fly app | URL |
|---|---|---|
| API + worker | `marrow` | https://api.marrow-health.com |
| MCP | `marrow-mcp` | https://marrow-mcp.fly.dev |
| Frontend | `marrow-ui` | https://marrow-health.com |
| Postgres | MPG `marrow-db-prod` (`d1zj5omzqwvryqkv`) — database `marrow` | via secrets |

### Develop (`develop`)

| Component | Fly app | URL |
|---|---|---|
| API + worker | `marrow-dev` | https://api-dev.marrow-health.com |
| MCP | `marrow-mcp-dev` | https://marrow-mcp-dev.fly.dev |
| Frontend | `marrow-ui-dev` | https://app-dev.marrow-health.com |
| Postgres | MPG `marrow-db-prod` (`d1zj5omzqwvryqkv`) — database `marrow_dev` | via secrets |

Deploy configs: `backend/fly.toml`, `backend/fly.mcp.toml`, `frontend/fly.toml` (dev) and `*.prod.toml` (prod). See [docs/fly-cutover-runbook.md](docs/fly-cutover-runbook.md).

## Branch workflow

- `develop` is the integration branch; PRs land there, run `.github/workflows/ci-develop.yml` (ruff + pytest + frontend lint/typecheck/build), then merge.
- Promotion to prod is a PR `develop` → `main`, gated by `.github/workflows/ci-main.yml` (same checks + prod-shaped frontend build).
- After CI green on push, Fly deploy workflows deploy API → MCP → frontend automatically.

## Running locally

```bash
./start.sh          # Both services
cd backend && uv run uvicorn app.main:app --port 8000 --reload   # Backend only
cd frontend && npm run dev   # Frontend only
```

## Key Paths

- Backend API: http://localhost:8000/api/v1
- Frontend: http://localhost:3000
- Database: Fly MPG in deployed envs; local tests use disposable Postgres via `testcontainers` (see `backend/tests/conftest.py`). `DATABASE_URL` must use asyncpg driver, e.g. `postgresql+asyncpg://...`.
- Photo storage: Tigris on Fly; `backend/photos/` locally

## Conventions

- Python: ruff for linting/formatting, target Python 3.10 (no 3.11+ syntax)
- Use `from __future__ import annotations` in all Python files
- Frontend: TypeScript strict, Tailwind for styling, shadcn/ui components
- API prefix: /api/v1
- Auth cookie name: ht_session

## Writing issues for sub-agents

Every implementation issue is a self-contained prompt for an agent that has no prior context. Use this structure, in this order:

1. **Problem (Why)** — one paragraph on what hurts now. Describe the constraint, not the solution.
2. **Goal** — one sentence on what changes when this is done.
3. **Sub-agent assignments** — table mapping each chunk to a sub-agent (`fastapi-backend`, `frontend-dev`, `data-engineer`, `data-scientist`, `devops`, `qa-engineer`). Each agent reads `~/.cursor/agent-memory/<agent-name>/MEMORY.md` before starting and writes back what's worth keeping when done.
4. **Proposed approach** — high-level technical approach + reasoning. Design, not implementation. Each issue gets a dedicated per-issue planning pass before code is written.
5. **Files** — *Existing modified* (paths + line numbers where known) and *New* (paths to create). Starting points, not exhaustive.
6. **Out of scope (non-goals)** — stated positively ("do not change X"). Agents cannot infer from omission.
7. **Boundaries** — tiered:
   - Always: actions the agent can take without asking
   - Ask first: actions that need user approval
   - Never: hard stops (secrets, force-push, destructive ops, `--no-verify`)
8. **Acceptance criteria / Definition of done** — concrete, runnable, objectively true/false. **Must include a live-server walkthrough** per `feedback_qa_e2e_live_server.md` — pytest passing is not the gate.
9. **Dependencies** — `Blocked by:` / `Blocks:` / `Required env / secrets:`.
10. **Rollback** — only when destructive or production-affecting. Trigger criteria + concrete revert steps.

**Anti-patterns to avoid:**
- Vague acceptance criteria ("user can log in" — write "POST /auth/login with valid credentials returns 200 and sets `ht_session` cookie")
- Implicit scope ("just clean things up while you're there" — list every file)
- Bundling unrelated work (one issue = one cohesive change)
- Skipping the live-server walkthrough in favor of "tests pass"
- Omitting boundaries — without them, agents take defensible-but-unwanted actions

**Sizing heuristic:** if an issue's sub-agent table has more than ~5 agents listed, or estimated effort exceeds ~5 person-days, split it.

References:
- [Osmani — How to write a good spec for AI agents](https://addyosmani.com/blog/good-spec/)
- [GitHub — Getting the best results from Copilot coding agent](https://docs.github.com/en/copilot/tutorials/cloud-agent/get-the-best-results)
- [GitHub — Reliable AI workflows with agentic primitives and context engineering](https://github.blog/ai-and-ml/github-copilot/how-to-build-reliable-ai-workflows-with-agentic-primitives-and-context-engineering/)
