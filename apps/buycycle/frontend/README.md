# Buycycle frontend

Standalone React/Vite with strict TypeScript, actual Primer from the shared
`@f0rge/primer` package, and TanStack Query, Router and Form. The Rust backend
owns contracts, validation, identity and permissions. This SPA contains no
tokens, identity bypass, alternate backend or client-only permission grant.

The Cloudflare Access email-code gateway handles sign-in. Fetches use the same
origin; the backend verifies the signed Access assertion independently. A 401 or
403 hides workspace data and offers `/cdn-cgi/access/login`. An uncached identity
probe retains only the verified opaque subject. Collection status, listings,
saved state and mutations are scoped to a unique identity epoch. A changed
identity aborts old requests, clears private query/mutation state and remounts all
forms/import drafts. Old replies cannot populate the next identity's cache.
Writes also carry an expected-identity precondition checked against the signed
backend principal; this header supplies no authentication or permission grant.

## Build and check

From the repository root:

```sh
npx nx run buycycle-frontend:typecheck
npx nx run buycycle-frontend:lint
npx nx run buycycle-frontend:test
npx nx run buycycle-frontend:build
npx nx run buycycle-frontend:codegen:check
npx nx run buycycle-frontend:e2e
```

Development defaults to `127.0.0.1:5178`, proxying `/api` to the local Rust API.
Use the app's complete development harness for database and signed test identity;
a Vite process alone does not provide authentication or persist data.

## Contract ownership

`npm run codegen -w @f0rge/buycycle-frontend` runs the Rust exporter, then
`openapi-typescript` against its OpenAPI output. Do not edit
`src/api/generated.ts` manually. `codegen:check` compares the client to the
committed Rust schema using Node; the required Rust contract test independently
compares that schema to the actual endpoint/type definitions. Both checks must
pass. macOS Cargo linking requires the documented local libpq installation.

`openapi-fetch` is the typed transport; TanStack Query wraps it. Mutations are
not automatically retried. Writes carry the saved revision and a 409 preserves
the visible form draft, shows the conflict and requires a deliberate reload/retry.
The shared public error adapter displays the documented error envelope and field
messages, with no raw response or internal-debug fallback.

## Data preservation

The app never writes or deletes legacy localStorage keys. The explicit browser
export reads `bikes:watch`, `bikes:log`, `bikes:costs` and their wheelset equivalents
on the current origin only. Before a URL or port cutover, repeat the export on
every old origin, browser profile and device; browser isolation prevents this SPA
from reading another origin's records.

The import flow previews watches, trades and **all costs** for both categories.
Conflicting values require an explicit stop/keep/use-imported choice. Identical
reimports keep trade multiplicity stable; unknown row metadata survives. Invalid
or unsupported records stop the import for review instead of being discarded.
The server validates the final state and archives the original source document
in the same transaction as its revision-checked write. Keep the original files
until reconciliation and restoration evidence is accepted.
Confirmation uses the exact validated body/revision; a refreshed server revision
or changed import choice invalidates the preview and requires review again.

Reference, sample-size, missing-observation and disappearance meanings come from
the Rust response. Display profit uses the legacy eleven cost assumptions; if
those inputs are missing, it remains unobserved rather than assuming zero. Daily
alerts retain their distinct dated collection thresholds and default cost model.
Source listings with missing/invalid prices are disclosed by count and source ID,
excluded from estimates/comparables and retained for reconciliation. No zero-price
listing or guessed observation is manufactured.

## Verification performed

- Strict typecheck, lint, production build and generated-client drift check passed.
- Seven logic/session tests cover dual-category import, repeat safety, duplicate trade
  multiplicity, conflicts, source preservation, read-only browser export, return
  calculations and unsafe-link rejection.
- Twenty-one Chromium tests against the **production build** pass with synthetic API
  boundary fixtures: denied, loading, retryable error, empty, watch/save,
  trades/costs, 409 draft retention, reviewed dual-category import, stale-preview
  refusal, unpriced-record disclosure, partial-collection warnings and slow-response
  identity switching.
- Desktop and 375px keyboard/overflow checks pass. Forty axe WCAG A/AA scans passed on
  all eight workspace views plus loading/denied states, in light and dark at both
  widths. Computed contrast and actual Primer button styling also pass in each
  scheme; the default canvas and foreground switch with the system preference.
- Shared Primer Storybook built and its real TanStack form was exercised in a
  browser for labelling, submission and keyboard focus.

These deterministic frontend tests do not substitute for the full Rust/real
PostgreSQL/signed-identity walkthrough, ARM64 artifact verification, provider
configuration evidence or a human screen-reader assessment. Those belong to the
coordinator's complete migration verification. Nothing here authorizes release.
