# Health Tracker

Personal daily symptom check-in app for Leo's health research vault.

## Stack

- Backend: FastAPI + SQLAlchemy + SQLite (Python 3.10)
- Frontend: Next.js 15 + React 19 + Tailwind 4 + shadcn/ui
- Auth: PIN-based session cookies (bcrypt)

## Running

```bash
./start.sh          # Both services
cd backend && uv run uvicorn app.main:app --port 8000 --reload   # Backend only
cd frontend && npm run dev   # Frontend only
```

## Key Paths

- Backend API: http://localhost:8000/api/v1
- Frontend: http://localhost:3000
- SQLite DB: backend/data/health.db
- Photo storage: backend/photos/
- Obsidian vault (Mac): /Users/leo/Library/Mobile Documents/iCloud~md~obsidian/Documents/Brain/
- Obsidian vault (container): /vault (bind mount of /mnt/nvme/home/leo/vaults/brain on Pi)
- Vault daily files: {vault}/Daily/Health-Logs/YYYY-MM-DD.md
- Vault photo attachments: {vault}/attachments/

## Conventions

- Python: ruff for linting/formatting, target Python 3.10 (no 3.11+ syntax)
- Use `from __future__ import annotations` in all Python files
- Frontend: TypeScript strict, Tailwind for styling, shadcn/ui components
- API prefix: /api/v1
- Auth cookie name: ht_session
- No emojis in Obsidian output files
