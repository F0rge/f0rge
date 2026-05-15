---
name: Thin-router scope: don't gate on pre-existing fat endpoints
description: New endpoints must be thin; modifying a fat endpoint to add a param is advisory, not blocker
type: feedback
---

The thin-router rule (see global `feedback_thin_routers.md`) is absolute for **new** endpoints in a PR. But when a PR modifies an already-fat endpoint to add a parameter, the existing violation is not the new PR's fault.

Example: `photos.py::upload_photo` has been fat (db.query, raise HTTPException, db.commit) for many releases. A PR that adds `meal_time: Optional[datetime.datetime] = Form(None)` and one extra line `meal_time=meal_time if meal_time is not None else now` is not making it worse — just bolting onto the existing pattern.

The rule:
- **New** endpoint (e.g. `PATCH /photos/{id}`) must be thin from day one.
- **Modified** existing fat endpoint: don't block on the pre-existing violations. List as advisory + recommend follow-up refactor.

**Why:** the global rule is "existing violations don't excuse new ones, but flag as follow-up". I read that as "any touch must refactor", which would balloon PR scope. The correct read: don't *copy* the pattern, but don't *forcibly refactor* unrelated code in this PR.

**How to apply:** when reviewing Phase 2, list per-endpoint:
- Brand new endpoint not thin → blocker.
- Pre-existing fat endpoint modified → advisory + follow-up task suggestion.
- Pre-existing fat endpoint untouched → don't even mention.
