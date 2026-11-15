# Buycycle ADR migration

Authorized 15 November 2026: implement the complete Buycycle migration in one PR,
with issue-sized commits. Buycycle comes first; the holiday-explorer pilot follows
later (P-010 update). Personal approved-person apps may use Cloudflare Access
email-code login; multi-user apps may choose Clerk (P-035 update). Buycycle uses
Cloudflare Access. Production cutover, merge and deployment remain unapproved.

## Assignments and commit sequence

| Work item | Primary | Independent review | Deliverable and dependency |
| --- | --- | --- | --- |
| I-01 Decisions and routing | f0rge-quality-testing, coordinator | security, backend, frontend | Record explicit decisions, exact ownership and acceptance matrix first |
| I-02 Data preservation | f0rge-data | backend, security, QA | Lossless five-table import, browser archives, idempotency, PostgreSQL tests and restore rehearsal |
| I-03 Backend and collector | f0rge-backend | data, frontend, security, QA | Actix/Diesel, authoritative contracts, safe shared errors, metrics parity and durable collector safeguards |
| I-04 Frontend | f0rge-frontend | backend, security, QA | Primer React bricks/Storybook, Vite/TanStack, generated client, all UI states and legacy browser-data transfer |
| I-05 Operations and release | f0rge-devops, f0rge-delivery, coordinator | security, QA | Private origin, verified Access assertions, controlled migration, backup/restore, tested ARM64 image and release receipts |
| I-06 Integrated evidence | f0rge-quality-testing, coordinator | independent specialists | Full local production-build walkthrough, error/denial/conflict paths, all ADR assessment and PR |

Workers follow `docs/agents/protocol.md`; exact paths resolve through the manifest.
Each work item is committed separately. Integration corrections may have follow-up
commits. No other feature branch is merged into this work.

## Acceptance matrix

- All five legacy tables reconcile by key, row count and canonical content hash,
  including unknown columns, nulls, history, original money units and metadata.
  The source database is unchanged by export; repeats are idempotent and conflicts
  refuse the transaction. The activation-day safety ledger is preserved or held.
- Watches, trades and all eleven cost settings for both categories can be exported
  without altering browser storage. Import previews distinguish conflicts and
  rejections, preserve original archives and use server revision checks.
- Rust APIs and the collector use shared services and actual PostgreSQL/Diesel.
  Legacy metric golden cases agree, including missing/sample-limited results.
- One collector owns the database; Luxembourg-day accounting survives restarts,
  failures and manual flags. Detail attempts never exceed 150; feed/detail pacing
  remains 1.6/2.2 seconds. 403/429 durably blocks before one 120-second backoff;
  incomplete runs never mark unseen listings disappeared.
- Access assertions require the correct asymmetric signature, issuer, audience,
  expiry and approved identity. Forged identity headers, missing/wrong tokens,
  expired tokens and unapproved identities disclose no app data. The new origin
  publishes no host ports. Cloudflare and provider configuration are verified
  separately from source tests before release.
- Actual Primer React, strict TypeScript, Vite and TanStack Query/Router/Form are
  exercised. Loading, empty, denied, error, stale, success and edit-conflict states
  have keyboard/browser evidence at desktop and 375px. Contracts/clients regenerate
  cleanly from Rust; field/permission/conflict errors use shared handling.
- A single local command starts disposable PostgreSQL, synthetic identity and the
  production app build. Tests make no real emails, paid calls, scrapes or production
  writes. PostgreSQL migration/restore and a complete local walkthrough pass.
- The exact ARM64 image is tested and its immutable identity retained; promotion
  never rebuilds it. Release approval is bound to commit/image/target/migration and
  recovery evidence. Provider receipt must prove the running image and readiness.
- Restore reconciles every application table. Post-backup divergence blocks
  activation; after PostgreSQL writes, recovery retains those writes instead of
  restarting stale Turso. Current services, data and browser storage remain intact
  throughout preparation.

## Release boundary

Code and local evidence establish only what was tested. They do not certify an
unreleased runtime, accept a proposed capacity/recovery target or supply Leo's
release approval. Any unavailable production configuration/evidence remains an
explicit failed preflight and a visible ADR gap, never a blanket compliance tick.
