---
name: Ruff format regressions are blockers
description: lines.extend([...]) trailing-comma patterns trip ruff's multi-line reformat; always check format on changed files
type: feedback
---

When auditing backend changes, run **both** `ruff check` and `ruff format --check` on the files modified by the PR. `ruff check` is not enough — formatting failures (which CI enforces) can slip past it.

Common regression pattern from this project: someone writes
```python
lines.extend([
    f"some-fmt-string: {var}",
])
```
inline. Ruff's stable formatter expands this to
```python
lines.extend(
    [
        f"some-fmt-string: {var}",
    ]
)
```
The first form is rejected by `ruff format --check`. Was clean on `main`, broken by this PR — a clear regression caused by the change in scope.

**Why:** caught in the meal_time/alcohol gate (obsidian.py). The author added the alcohol/caffeine block right above an existing `lines.extend([...])`, but the proximity of the change made ruff re-flow the surrounding code differently.

**How to apply:** when reporting Phase 1, compare format-check output on the changed file between `main` and HEAD. If it was clean on `main` and dirty on HEAD, list as a **blocker** under "Issues to Fix" with responsible agent. Pre-existing format failures on other files are advisory.
