---
name: pre-existing lint errors — do not fix in unrelated PRs
description: There are two pre-existing lint errors in the codebase that are not my responsibility to fix
type: feedback
---

The project has two pre-existing lint issues before this branch:
1. `components/auth/pin-pad.tsx:19` — `react-hooks/set-state-in-effect` error (setState called synchronously in useEffect).
2. `components/checkin/checkin-form.tsx` — `@next/next/no-img-element` warning on the existing-photos grid `<img>`.

**Why:** These existed before the feature branch. Fixing them in an unrelated PR causes noise and churn.
**How to apply:** When running `npm run lint` and seeing these two errors, confirm they are pre-existing before treating them as regressions. Only fix them if explicitly asked.
