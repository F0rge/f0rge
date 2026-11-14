# Buycycle first-slice verification

Scope: migration brief, synthetic clickable mockup and legacy tracker safety fixes.
No production data, browser storage, feed key, Pi service or provider setting was
accessed or changed. This is a local review record, not release approval.

## Reproduce and verify the safety failures

Before the fixes, the first three new regressions failed against the actual
tracker functions with temporary Turso data and fake outbound transport:

- A first HTTP 429 caused two upstream calls instead of stopping after one.
- An unterminated feed could report complete and mark an old listing gone.
- Unrecognized detail HTML could create a successful detail record.

Independent review reproduced these failures and an additional case where a
present listing with no usable price could be marked disappeared. The final
suite covers all of them, plus successful collection, persistence and failure
paths through the real tracker/sidecar code. Only external I/O, sleep and clocks
are replaced; subprocess cases exercise actual lock and restart behavior.

## Checks

```sh
NX_DAEMON=false NX_ISOLATE_PLUGINS=false npx nx run-many \
  -t=lint,format-check,test --projects=buycycle --skip-nx-cache --output-style=static
npm run agents:check
git diff --check
```

- Ruff lint and formatting passed.
- **42 tests passed:** 12 existing behavior tests plus 30 safety tests.
- Agent routing/generated-adapter consistency and whitespace checks passed.
- Independent quality and security review found no remaining blocking findings.

The new tests cover the combined daily 150-detail-attempt budget across kinds
and separate CLI processes, 403/429 block persistence, pending-request recovery,
ledger-write failures, interrupted requests, corrupt state, conservative legacy
bootstrap, Luxembourg date changes, exclusive locking before DB access, lock
release after process termination, redirects, failed-detail bookkeeping and
malformed/truncated/duplicate/exhausted pagination. A real loopback-only HTTP
server verifies that redirects cannot hide an extra request. No real upstream
request is made by these tests.

## Local runtime smoke

Built the existing Dockerfile locally for **linux/arm64**. Started that image
with `--network none` and a task-owned temporary `/data` filesystem; no host or
production data volume was mounted. The actual tracker ran with
`--no-scrape --no-fetch` using six synthetic records per category. Outbound
transport was additionally denied in the smoke harness.

- Listing, price-history and detail rows were identical before/after the offline
  run; both categories generated their existing data/metadata/alerts formats.
- The actual static servers returned HTTP 200 on container-local ports 8095 and
  8096, and each served six synthetic rows from `data.json`.
- The local image identity and disabled network were inspected. This local build
  is not a published registry artifact, CI attestation or production promotion.

A temporary QA layer over that same ARM64 image adds pytest and the safety test
file, then executes the safety suite with networking disabled. Dependency
installation happens during the local build, not during the isolated tests.
All **30 safety tests passed** on Linux ARM64/Python 3.12; the only warning was
pytest being unable to write its optional cache under the non-root app directory.

## Served clickable mockup walkthrough

Served the committed design artifact with its local vendored Primer styles on
localhost. The page contains synthetic page-memory records only.

Verified:

- Bikes and wheelsets; search/no matches; comparable disclosure; watch additions.
- Trade/cost previews; invalid negative trade input is rejected without adding a row.
- Import preview includes watches, trades and costs for both kinds; conflict
  choices work; invalid samples disable simulated import.
- Loading, empty, load-error/retry, denied and stale states. Denied state hides
  the sample content and collection summary; it is not real authentication.
- Keyboard activation of native disclosure; navigation moves focus to the page heading.
- Responsive table/cards at 1440px and 375px: document width equals viewport
  width; no horizontal page overflow. Browser console had no warnings/errors.
- Reload resets all sample changes; no real storage or collector was used.

This is not full WCAG/screen-reader certification or an authenticated full-stack
journey. Insights, Alerts and Method screens, complete valuation displays and
all real import fields are future mockup/app work; this draft previews selected
core journeys and awaits Leo's review. The Rust/PostgreSQL/React migration is
not implemented by this first slice.

## Data and operational boundary

The five legacy Turso table definitions, calculation logic, output formats,
ports and private Pi configuration remain unchanged. Watchlists, trade records
and cost assumptions in existing browser origins are untouched.

New operational state is stored next to the canonical DB as
`<db>-tracker-safety.json`; its matching `-tracker.lock` provides local process
exclusion. Reserve-before-I/O plus atomic replacement/fsync preserves quota and
uncertain outcomes. Missing ledger with existing data holds collection for the
activation day. Corrupt/unsupported ledgers fail closed and are preserved.
Offline rebuilding still works. Redirects are refused, so a changed upstream
redirect or response shape may now leave details incomplete rather than being
silently accepted.

Back up the DB and ledger together. Unknown current-day usage or an interrupted
request must not be “fixed” by resetting the counters. A reviewed recovery must
preserve original evidence and conservatively hold/exhaust that day's budget;
this PR adds no automatic ledger-repair or production-operation command.

No merge/deploy is authorized. A later approved release needs its own live target,
backup/recovery and artifact evidence. If rolling back this safety version later,
keep collection paused while preserving DB/ledger: the old code does not honor
the new safeguards. A code revert alone is not a safe instruction to resume it.
