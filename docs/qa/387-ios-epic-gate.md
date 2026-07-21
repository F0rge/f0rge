# QA Gate — Epic #387 Marrow iOS (feat/marrow-ios-387)

Gate run 2026-07-18/19 on the worktree branch (8 commits + simplify-pass working tree). Backend E2E against local ht-postgres + live uvicorn with the reminder loop running.

## Quality matrix

| Check | Result | Detail |
| --- | --- | --- |
| ruff check + format | pass | clean, 407 files |
| Backend pytest (testcontainers) | pass | 839 passed, incl. `test_alembic_upgrade_head` (migration chain 001→046) |
| Frontend lint / typecheck / test / build | pass | eslint, tsc, vitest 4/4, next build all clean (re-run after the one QA fix) |
| OpenAPI drift (CI-exact) | pass | export → codegen → `git diff --exit-code` clean |
| iOS build | pass | `xcodebuild` generic/iOS Simulator → BUILD SUCCEEDED |
| Swift codegen determinism | pass | `generate-client.sh` re-run → identical SHA-256 for Client.swift/Types.swift |
| Thin-router audit (devices, health_metrics, auth) | pass | grep for logic/db/raise in routers → zero hits |

## Live-server E2E (bearer API surface = the iOS contract)

| Path | Result | Evidence |
| --- | --- | --- |
| Signup/login return `token`; bearer `/auth/me` | pass | signup + login both return JWT; `/auth/me` 200 correct user; garbage bearer 401 |
| `POST /health-metrics/samples` | pass | 2 partial days → 200; identical repost idempotent; partial re-post merges (hrv+rhr kept, sleep added); `source=ios_healthkit` |
| RLS isolation | pass | user B GET of A's metric date → 404; B's notifications `[]` |
| Device takeover | pass | B registers token, A re-registers same token → A owns it (B DELETE 404, A DELETE 204); re-register 200, re-DELETE 404 |
| Reminder loop live | pass | treatment doses_per_day=1, `reminder_times=["21:24"]` (set via psql — field is deliberately not exposed on the treatments API); notification inserted at 19:24:51Z with correct payload + dedupe_key; after 2+ further in-window ticks still exactly 1 row (1 distinct dedupe_key next day too) |
| APNs unconfigured warning | pass | startup log: "Push delivery is disabled; in-app reminder notifications still work" |
| Web bell (Playwright) | pass | login as A → Profile bell badge "1 unread" → list renders "Dose reminder: QA Gate Med — dose 1"; ingested resting HR (48 bpm) also visible in profile metric trends |
| Legacy `/import` | partial | cookie-JWT path verified live (200, upserted); static-token path not exercisable locally (`HEALTH_IMPORT_TOKEN` unset in local .env; bad bearer → 401). Prod token path is in Leo's checklist below |

## Fixes made during the gate

- `apps/marrow/frontend/lib/api/hooks/notifications.ts` — added `dose_reminder` case to `notificationCopy` (was falling through to generic "New activity"). Lint/typecheck re-run clean; verified rendered in browser.

Environment note (not a code bug): local ht-postgres carried another branch's 045/046 in `alembic_version`, so this branch's 045 was skipped and the loop crashed on `user_settings.timezone`. DB dropped/recreated, full chain 001→046 applied cleanly, loop clean thereafter.

## Karpathy diff audit

`git diff develop...HEAD` (55 files) + working tree: every file traces to plan §5 (backend auth/ingest/reminders/devices + migrations 045/046 + tests, `apps/marrow/ios/**`, contract files, uv.lock/pyproject for aioapns, iOS README) or the recorded simplify pass (test-helper dedupe into `tests/helpers.py`/conftest, push-after-commit refactor, signup token) or the QA fix above. Zero changes outside `apps/marrow/{backend,ios,frontend}` + `docs/`.

## Deferred to Leo (physical devices) — from issue #396

- [ ] Leo + Beatriz both install via TestFlight and log in to their own accounts
- [ ] HealthKit permission flow on both phones; fresh health data lands in prod under each correct user_id (DB-verified per epic's RLS query recipe)
- [ ] Dose reminder fires on a closed app at the right local time on both phones; "Log dose" from the lock screen increments treatment_log (DB-verified)
- [ ] Reminder dedupe holds across a backend deploy/restart mid-slot
- [ ] RLS spot-check: neither account can read the other's health rows via the API
- [ ] Legacy Auto Export import still functional (not yet decommissioned) — *API-verifiable part done locally: cookie-JWT path returns 200 and upserts; the static `HEALTH_IMPORT_TOKEN` bearer path could not be exercised (token unset in local .env) — verify once against prod with the real token*

Also Leo-only: Apple Developer enrollment, APNs .p8 creation + `fly secrets set` (see `apps/marrow/ios/README.md`).

## Test data left in local ht-postgres (`health` DB)

DB was recreated during the gate (prior sessions' data gone). Left behind: users `qa_usera`/`qa_userb` (@example.com), A's health_metrics for 2026-07-15..17, treatment "QA Gate Med" (reminder_times 21:24 — will re-fire daily if a server is left running), 1 dose_reminder notification, auto-saved check-in entries for A (07-18, 07-19).

## Gate decision

**PASS** — all agent-runnable checks green; one 2-line frontend fix folded in; physical-device checklist deferred to Leo as planned.
