# QA Engineer Memory

## Project Commands

```bash
# Backend
cd backend
uv run ruff check .
uv run ruff format --check .
uv run uvicorn app.main:app --port 8000 --reload
uv run pytest tests/ -v

# Frontend
cd frontend
npm run dev              # Dev server :3000
npm run build            # Production build
npm run lint             # ESLint
```

## Agent Responsibility Map

| Agent | Owns |
|-------|------|
| fastapi-backend | Routers, services, dependencies, models, schemas, API integrations |
| frontend-dev | React components, pages, hooks, styles, Next.js features |
| data-scientist | Vision prompts, ingredient recognition, dietary tag logic |
| data-engineer | ETL pipelines, dietary databases, ingredient normalization |

## Architecture rules to enforce

From CLAUDE.md:
- `from __future__ import annotations` in all Python files
- Python 3.10 target (no 3.11+ syntax in runtime contexts)
- API prefix `/api/v1`
- Auth cookie name `ht_session`
- No emojis in Obsidian output files
- ruff for Python linting/formatting
- TypeScript strict, Tailwind for styling, shadcn/ui components

## Obsidian Output Checks

When vault rendering changes, verify:
- Frontmatter is valid YAML
- Tags include `daily-check-in`, `symptom-log`
- Photo embeds use `![[attachments/filename]]` syntax
- No emojis in output
- Links to Symptoms-Master & CURRENT-HYPOTHESIS in footer

## Lessons learned (debugging shortcuts that paid off)

### Tail backend logs FIRST when a user reports a UI error
UI toast messages routinely mask 500s from a different layer. The user reports "Failed to delete photo" or "Failed to save uploaded file"; the real failure is upstream (entry POST returning 500, background task throwing, etc.) and the toast is just whatever `.catch()` happened to be on the immediate call.

Before reading frontend code, always:
```bash
ssh rpi "docker logs --tail 100 $(docker ps --format '{{.Names}}' | grep mk404) 2>&1 | tail -50"
```
Look for 500s, IntegrityError, AttributeError. The actual failing endpoint is often NOT the one named in the toast.

*Why:* PR #5 (stool_normal NOT NULL outage) presented as "Failed to save uploaded file" — actual failure was entry POST 500. Spent investigation time reading photo upload code before checking logs.

### After any PR adding files outside `app/`, verify Dockerfile ships them + check volume mounts
Two related production silent-failures one issue away:

1. **Dockerfile doesn't auto-ship new directories.** The food-analysis feature deployed for weeks with dietary tables permanently empty because `Dockerfile` only `COPY ./app ./app` — `backend/scripts/` and `backend/data/` were never in the image. Every ingredient analysis silently rendered "?" badges.

2. **Volume mounts shadow image-baked files.** Even after fixing the COPY, the first attempt put files at `/app/data/` which is volume-mounted (`health-tracker-data`) — files were invisible at runtime. Had to use a separate path `/app/data-seed/`.

When reviewing a PR that adds `scripts/`, `data/`, `seeds/`, `templates/`, etc.:
- Grep the Dockerfile for that directory name
- Check existing volume mounts: `ssh rpi "docker inspect <container> --format '{{json .Mounts}}'"`
- The new path must not collide with a volume mount destination

*Why:* Issue #20, critical. Discovered only when manually verifying PR #19's alias coverage on prod — dietary tables were empty for the entire deployment lifetime.
