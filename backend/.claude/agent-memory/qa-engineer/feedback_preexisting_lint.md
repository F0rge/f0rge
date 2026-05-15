---
name: Pre-existing lint not blocking
description: F821 forward-refs on Photo/Entry/PhotoAnalysis and pin-pad.tsx set-state-in-effect are pre-existing
type: feedback
---

The following ruff/eslint issues are **pre-existing** on `main` and must not block a PR:

- `app/models/entry.py` F821 `Mapped[list[Photo]]` — forward reference, runtime-safe via SQLAlchemy string-form relationship.
- `app/models/photo.py` F821 `Mapped[Entry]`, `Mapped[Optional[PhotoAnalysis]]` — same.
- `app/models/photo_analysis.py` F821, `app/models/photo_ingredient.py` F821 — same.
- `frontend/components/auth/pin-pad.tsx` `react-hooks/set-state-in-effect` error.
- `frontend/components/checkin/checkin-form.tsx` `<img>` instead of `next/image` warning.

**Why:** the project ships with these and they shouldn't block unrelated PRs.

**How to apply:** when reporting Phase 1, ignore these specific findings on unchanged files. Confirm a finding is pre-existing by `git stash && uv run ruff check <file> && git stash pop` — if it persists on main, it's not this PR's problem. Flag as advisory if relevant, blocker only if newly introduced.
