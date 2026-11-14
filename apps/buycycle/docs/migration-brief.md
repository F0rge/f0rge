# Buycycle migration brief — first delivery

Status: the migration plan and this first delivery are authorized. The clickable
UI is a design draft for Leo's review; the final migrated UI is not approved or
implemented by this PR. No merge or production deployment is authorized.

## Problem and outcome

Buycycle is a useful private bike and wheelset deal finder on the Pi. Its
Python/Turso/static-page implementation still needs gradual migration to the
[accepted architecture](../../../docs/adr/README.md). The immediate risk is the
collector's inconsistent enforcement of its documented daily safety policy.

This delivery makes that policy testable, fixes the tracker safeguards, and gives
Leo a clickable design to review before the app rewrite. It preserves the existing
data formats and pricing meanings. It does not claim the app now complies with
the target stack.

## This delivery

- Add offline regressions and tracker safeguards for the global daily detail
  request budget, blocking, overlap, repeat invocations, incomplete feeds and
  unsuccessful detail retrieval.
- Keep existing Turso history, published data formats, metric definitions and
  browser-owned records intact. Any added safety bookkeeping is separate from
  the legacy data schema; implementation and recovery behavior must be covered
  by the tracker tests and PR evidence.
- Add [the clickable mockup](migration-mockup.html) using the existing vendored
  Primer styles and synthetic, in-memory records only.
- Keep Buycycle private on the Pi with its current ports and access arrangement.
  This slice changes no DNS, gateway, provider, credential or deployment settings.

## Safety outcomes

The existing policy is 1.6 seconds between feed requests, 2.2 seconds between
product-detail requests, and at most 150 detail HTTP attempts in a Luxembourg day
across both categories and all invocations. Failed attempts count. A 403/429 is
recorded as blocked, followed by one 120-second backoff and no further network
requests that collection day. A successful retry must not quietly resume
collection: the documented stop-after-block policy is the intended behavior.

Only one collector may own the database/output at a time. Repeated invocations,
manual flags and process restarts must not reset the budget or block state.
Interrupted/truncated/malformed feeds must remain incomplete and must not mark
unseen listings disappeared. Failed detail retrieval must not claim success.

If legacy request consumption cannot be proved, treat the activation day's
budget conservatively and keep collection paused until the next Luxembourg day.
Offline rendering can still be tested without consuming or resetting the budget.
The safety state must fail closed if corrupt or unavailable; no real data or
safety ledger may be discarded as a routine recovery step.

## Design to review

From the repository root, serve the source locally:

```bash
python3 -m http.server 8767 --bind 127.0.0.1 --directory apps/buycycle
```

Open `http://127.0.0.1:8767/docs/migration-mockup.html` or the
[local file](migration-mockup.html). Stop the preview server after review.
The mockup previews:

- Bikes and wheelsets, searchable deals, responsive cards/table and comparable
  disclosure; missing metrics remain explicit.
- Watchlist, trade records and cost assumptions as distinct, understandable views.
- A migration preview that includes watches, trades **and costs** for both kinds,
  shows conflicts/rejections, and makes the user's decision visible.
- Collection status and ready, loading, empty, error, denied and stale states.

Every example is synthetic. Interactions change only page memory and disappear
on reload. There is no real sign-in, collector/API connection, browser-storage
access, file import or server persistence. The mockup loads local styles only.
It is not a React build or proof of backend authorization/accessibility compliance.

### State and walkthrough matrix

| Journey | Success state | Failure or alternate state | Acceptance evidence |
| --- | --- | --- | --- |
| Browse bikes/wheels | Change category, search, open comparable details, add a watch | No results; data load failure; last-good data is stale | Local served mockup on desktop and 375px, no page overflow; deterministic states work |
| Watchlist | Added synthetic listing appears and can be removed | Empty list | Changes remain page-local; reload restores examples |
| Trade entry | Valid amount/date produces a visible preview row | Required fields/invalid amount are rejected | Native form validation and visible status; no real record write |
| Cost assumptions | Edit values and preview them | Invalid/nonfinite/negative values are rejected | Values are labelled as assumptions, not current fee advice |
| Bring saved data | Preview watches/trades/costs for both kinds | Conflict choices and invalid sample are explicit | Review then simulated import; no actual browser state/file read |
| Private access | Approved-person state is illustrated | Denied state hides app content | Denial is a design state only; actual access tests belong to the future app |
| Collection health | Last successful collection and safe schedule are understandable | Blocked/partial/stale is explicit | No collector runs from a preview control |

## Data and behavior that must survive the later migration

Database import alone is insufficient. Watchlists, trade records and assumptions
live separately in localStorage for every previously used scheme/host/port and
browser profile/device. Inventory all such origins, including LAN and tailnet
aliases at both ports. Export each before a future URL change; the current export
contains costs, but the current import does not restore them. The future importer
must validate, preview, reconcile and repeat safely without silent overwrites.
No real browser state is read or changed in this delivery.

Preserve listing IDs, observed history, first/last seen and disappearance meaning,
nulls and current money units. Characterize rounding, confidence/risk quartiles
and timezone behavior before moving calculations to Rust. Keep these invariants:

- Comparables exclude self and gone listings; bikes match brand/model and year
  within ±1 when known; wheels also distinguish brake/rim.
- Reference is the eligible median with at least three comps; average ask is a
  separate mean. Profit and alerts keep using the reference, not average/Z-score.
- Z-score is missing below two comps or zero spread, with low-sample warnings.
  €/day, disappearance share and relative disappearance time retain their history
  and sample-size limits.
- Next up is strictly more expensive, with the existing tie/age/lower-bound rules.
- Disappeared means sold **or withdrawn**, not a confirmed sale. Asking price is
  not realized sale price. Never invent missing observations.
- Preserve all user costs and profit/ROI assumptions. Historical fee notes remain
  dated assumptions until their sources are revalidated in the implementation
  brief; the mockup's figures are illustrative, not live market/fee facts.

## Proposed next milestones

1. Review this mockup and agree the final journey/state matrix and measurable
   acceptance criteria with Leo (P-008/P-009).
2. Verify holiday-explorer pilot evidence or complete that pilot before broader
   platform adoption (P-010); Buycycle does not silently replace it.
3. Establish Rust/Nx affected CI, small shared Rust plumbing, actual shared Primer
   React bricks/Storybook/form adapters, and generated Rust contracts/clients.
   Classify new library paths in the routing manifest before implementation.
4. Rehearse dedicated PostgreSQL import/reconciliation and browser-state transfer
   with synthetic fixtures. Use actual PostgreSQL in the new integration tests.
5. Implement Rust/Actix/Diesel business logic and the scheduled command, followed
   by standalone React/strict TypeScript/Vite and TanStack Query/Router/Form.
6. Agree private identity/gateway access, measured operating targets, protected
   backups/restore, and exact tested ARM64 image promotion before cutover.
   The existing no-domain constraint is not changed by this slice. Any later
   route change needs an approved design preserving private reachability.

The identity vendor, Rust contract/client generator, Diesel asynchronous adapter,
shared Primer package seam, and measured freshness/resource/recovery/retention
values need evidence and a recorded decision at their implementation stage.
C-001/C-002 remain conditional; neither Zod nor a particular testing toolkit is
adopted by this design draft. A new heavyweight scheduler or Airflow is not
required for the single daily app job.

## Review and release boundary

The PR must show the exact safety tests/checks executed, their results, the local
mockup walkthrough, independent findings and remaining ADR gaps. Passing a
synthetic test or approving a mockup is not production-release approval.

Any later approved cutover must stop/fence the old writer, preserve consistent
backups and browser exports, reconcile every source record, and account for the
old day's unknown request consumption. After new data/user edits exist, rollback
must preserve them; restarting stale Turso is not a zero-loss recovery plan.

This delivery changes no running Pi service or production data. Before any later
release, follow the [release hold](../../../.github/deploy/README.md) and obtain
Leo's explicit approval for the exact artifact, migration and recovery scope.
