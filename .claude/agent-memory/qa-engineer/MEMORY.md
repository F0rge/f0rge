# QA Engineer Memory

## Project Commands

```bash
# Backend
cd backend
uv run ruff check .
uv run ruff format --check .
uv run uvicorn app.main:app --port 8000 --reload
uv run pytest tests/ -v  # No tests exist yet

# Frontend
cd frontend
npm run dev              # Dev server :3000
npm run build            # Production build
npm run lint             # ESLint
```

## Quality Checks

| Check | Command | Status |
|-------|---------|--------|
| Python lint | `uv run ruff check .` | Available |
| Python format | `uv run ruff format --check .` | Available |
| Frontend build | `npm run build` | Available |
| Frontend lint | `npm run lint` | Available |
| Backend tests | `uv run pytest tests/ -v` | No tests yet |
| Frontend tests | N/A | No test infrastructure |
| E2E tests | N/A | No Playwright setup |

## Agent Responsibility Map

| Agent | Owns |
|-------|------|
| fastapi-backend | Routers, services, dependencies, models, schemas, API integrations |
| frontend-dev | React components, pages, hooks, styles, Next.js features |
| data-scientist | Vision prompts, ingredient recognition, dietary tag logic |
| data-engineer | ETL pipelines, dietary databases, ingredient normalization |

## Known Technical Debt

- Business logic currently in routers (not yet refactored to service layer)
- No app/dependencies/ directory for Depends() factories
- No test files exist (backend or frontend)
- No E2E test infrastructure (no Playwright)
- Manual DB migrations instead of Alembic
- Photo upload has no image analysis

## Architecture Rules to Enforce

From CLAUDE.md:
- `from __future__ import annotations` in all Python files
- Python 3.10 target (no 3.11+ syntax)
- API prefix /api/v1
- Auth cookie name ht_session
- No emojis in Obsidian output files
- ruff for Python linting/formatting
- TypeScript strict, Tailwind for styling, shadcn/ui components

## Obsidian Output Checks

When vault rendering changes, verify:
- Frontmatter is valid YAML
- Tags include daily-check-in, symptom-log
- Photo embeds use ![[attachments/filename]] syntax
- No emojis in output
- Links to Symptoms-Master & CURRENT-HYPOTHESIS in footer
