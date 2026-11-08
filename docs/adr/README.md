# Architecture decision records

This index is the repo copy of the 7 November 2026 register: 64 accepted decisions (`P-001`–`P-064`) and 2 conditional selections (`C-001`, `C-002`). The IDs are the temporary register IDs. They are not older ADR numbers.

These files become the canonical decisions after review, approval, and merge. Until then they are the proposal in this pull request. The planning Page remains a planning aid and is not a second policy copy.

## Provenance

The decisions were reconstructed from the 7 November 2026 architecture conversation and durable-memory recall. A transcript search in that research pass did not return the original conversation. Governance, some auth and accessibility items, and some operational details rely on the parent-provided history where memory had no matching fact. This is not a claim that every earlier acceptance was re-read as a verbatim quote. Later explicit approvals override older memory. Do not treat this file as independently verified original minutes.

## How to read a record

- **Accepted** is agreed policy. It is not a statement that the repo already works that way.
- **Conditional** is not accepted policy. Do not make it mandatory.
- **Proposed enforcement** names a check that is not installed. Do not describe it as CI.
- **Static evidence** is what a read-only look at `f155a2ba` found. It is not a live Railway, Coolify, Pi, or database grant check.
- **Approved exception:** none. Legacy apps are migration inventory. Do not call them grandfathered.

## New work versus what is already here

New apps use the accepted stack: Rust and Actix Web for HTTP, Diesel for PostgreSQL, PostgreSQL as the database, a standalone React frontend with strict TypeScript, Vite, actual Primer, TanStack Query, TanStack Router, and TanStack Form. Shared UI bricks are Primer components, not a lookalike. Leo approves every production release. Do not enable auto-merge. Until an `adr-coverage` check exists, the filled 66-row checklist (recorded, enforcement, implementation, exception) belongs in the pull-request description. The table below is the index, not that checklist. Checking a box is not proof, and this repo does not yet have a mechanical checker.

Apps already in the tree — Marrow, Firstout, dk, buycycle, environment-monitor, storefront/Vellano, Airflow, and the Swift iOS client — keep their current commands and safety rules. Their Python, Next.js, Medusa, Carbon, shadcn, Mantine, Turso, SQLite, and Fly files are legacy inventory. They are not approved exceptions and they are not migrated by these records.

`C-001` (generated Zod from a Rust contract into TanStack Form) and `C-002` (Vitest, Storybook browser tests, Playwright journeys) stay conditional.

## Open choices

These are not decisions. Do not invent a selection.

- Airflow hosting, executor, capacity, and secure routes between Railway, a separate Airflow project, and the home Pi. Cloud independence from the home Pi was not accepted. Namespaces, pools, and experimental multi-team mode are not hard tenant isolation; that limit is recorded on `P-060`, not as a new decision.
- How a separate Airflow project would reach app APIs. Railway private DNS does not cross projects. Do not share app databases to solve that.
- Airflow bundle packaging and whether a git bundle pin also pins helpers, the Rust API, or retained inputs. It does not.
- Durable queue and the lighter scheduler. Apalis was a candidate, not a standard. Diesel transaction participation is unproven because Diesel is not in the tree.
- Repo-wide permission library and auth vendor. RBAC plus ABAC, and the two auth modes, are accepted. Clerk is not a repo-wide mandate.
- Contract and client generator. Rust definitions stay authoritative. Zod stays conditional.
- Package-manager choice, tool versions, and Dependabot versus Renovate. Nx remains the current monorepo tool. The register does not select a new build orchestrator.
- Numeric runtime, freshness, memory, retry, retention, backup, and recovery targets. Numbers already in scripts are not approvals.

## Release and checklist

Leo approves every production release, bound to a commit and an artifact digest once that mechanism exists. It does not exist yet. Do not enable auto-merge. Do not merge or deploy without that approval. Existing GitHub workflows and host docs still describe automatic paths. Those paths are not an approved exception, and editing these records does not turn them off or authorize them.

Every pull request into `main` includes this checklist for all 66 IDs: recorded, enforcement, implementation, exception. Honest values are pass, partial, fail, pending, not-applicable, or approved-exception. `fail` means the change contradicts an accepted decision or a conditional was treated as mandatory. A human still has to judge rationale. There is no `adr-coverage` job in CI. The filled checklist for this change stays in the pull-request description.

## Index

| ID | Status | Decision | Record |
| --- | --- | --- | --- |
| P-001 | Accepted | Repo-wide ADRs are authoritative. AGENTS.md points to them; no drifting policy copies. | [P-001](governance.md#p-001) |
| P-002 | Accepted | One default stack, exceptions approved by Leo. Apply new standards to new apps first; migrate existing apps gradually. | [P-002](governance.md#p-002) |
| P-003 | Accepted | Every PR to main includes an ALL-ADR compliance checklist, with statuses and justified exceptions. | [P-003](governance.md#p-003) |
| P-004 | Accepted | Deterministic automated architecture checks block merge and release where enforceable; exceptions need Leo. | [P-004](governance.md#p-004) |
| P-005 | Accepted | Independent agent review plus CI, not the implementing agent alone. | [P-005](governance.md#p-005) |
| P-006 | Accepted | Leo approves every production release. | [P-006](governance.md#p-006) |
| P-007 | Accepted | Recreate development agents later with repo-aligned instructions. | [P-007](governance.md#p-007) |
| P-008 | Accepted | Before an app or substantial feature: agree a short brief, testable outcomes and clickable mockup with Leo. | [P-008](product.md#p-008) |
| P-009 | Accepted | Design and test loading, empty, error, denied, success and edit-conflict states. | [P-009](product.md#p-009) |
| P-010 | Accepted | Use the holiday explorer as the platform pilot; no standalone off-platform deployment. | [P-010](product.md#p-010) |
| P-011 | Accepted | Rust for new backends; transition existing Python/FastAPI backends gradually. | [P-011](backend.md#p-011) |
| P-012 | Accepted | Actix Web is the default Rust HTTP framework, not Axum. | [P-012](backend.md#p-012) |
| P-013 | Accepted | Diesel is the PostgreSQL ORM; asynchronous integration is the planned direction. | [P-013](backend.md#p-013) |
| P-014 | Accepted | Layer each app into handlers, business services and database access; add domain modules where useful. No microservices by default; API and app jobs reuse business services. | [P-014](backend.md#p-014) |
| P-015 | Accepted | Small shared Rust plumbing libraries; app-specific business rules, database models and migrations stay app-local. | [P-015](backend.md#p-015) |
| P-016 | Accepted | PostgreSQL is the default database for new apps. | [P-016](data.md#p-016) |
| P-017 | Accepted | Each app owns its data. Other apps and Airflow use approved APIs, never direct cross-app database reads/writes. | [P-017](data.md#p-017) |
| P-018 | Accepted | On Pi, one PostgreSQL cluster with separate app databases and restricted app logins. | [P-018](data.md#p-018) |
| P-019 | Accepted | On Railway, each app keeps its own project and PostgreSQL service; no giant shared F0rge app project. | [P-019](data.md#p-019) |
| P-020 | Accepted | Tested migrations run as a controlled step in an approved release, not independently at each instance startup. Preserve compatibility; destructive changes need explicit approval and recovery. | [P-020](data.md#p-020) |
| P-021 | Accepted | Rust endpoint/request/response definitions are authoritative; generate the API contract and typed React clients, with compatibility checked in CI. | [P-021](api.md#p-021) |
| P-022 | Accepted | Shared API error format and shared frontend handling for field errors, permission failures and edit conflicts; no internal debug-detail leaks. | [P-022](api.md#p-022) |
| P-023 | Accepted | Standalone React frontend; Rust owns the backend. | [P-023](frontend.md#p-023) |
| P-024 | Accepted | Strict TypeScript for React apps and shared frontend packages. | [P-024](frontend.md#p-024) |
| P-025 | Accepted | Vite is the default frontend development/build tool. | [P-025](frontend.md#p-025) |
| P-026 | Accepted | Use actual Primer as the single shared design system, not merely a similar appearance. | [P-026](frontend.md#p-026) |
| P-027 | Accepted | Default Primer tokens unless Leo specifies a custom theme; custom themes retain accessibility. | [P-027](frontend.md#p-027) |
| P-028 | Accepted | Share reusable UI bricks repo-wide, not app-specific screens/business rules. | [P-028](frontend.md#p-028) |
| P-029 | Accepted | Storybook is the place to inspect and test shared UI bricks. | [P-029](frontend.md#p-029) |
| P-030 | Accepted | TanStack Query around generated API clients is the standard server-data approach. | [P-030](frontend.md#p-030) |
| P-031 | Accepted | TanStack Router is the default router. | [P-031](frontend.md#p-031) |
| P-032 | Accepted | TanStack Form with shared, tested Primer adapters. | [P-032](frontend.md#p-032) |
| P-033 | Accepted | Frontend validation helps the user; Rust validates authoritatively. Keep both coherent without assuming business/permission rules can all be generated. | [P-033](api.md#p-033) |
| P-034 | Accepted | WCAG 2.2 AA target, with automated checks plus keyboard and screen-reader checks on core journeys. | [P-034](frontend.md#p-034) |
| P-035 | Accepted | Two auth modes: private approved-person access and customer accounts. | [P-035](security.md#p-035) |
| P-036 | Accepted | Use shared verified identity adapters; backend identity must be trustworthy. | [P-036](security.md#p-036) |
| P-037 | Accepted | Combine RBAC and ABAC as needed through shared permission mechanisms; backend checks are authoritative and tenant-scoped. | [P-037](security.md#p-037) |
| P-038 | Accepted | Keep personal apps simple; enforce organization data isolation when agreed scope includes multiple customer organizations. | [P-038](security.md#p-038) |
| P-039 | Accepted | Development agents may read real personal/customer data only when needed for the assigned task, read-only and with sensitive fields masked. | [P-039](security.md#p-039) |
| P-040 | Accepted | One standard command starts the full app locally with database and safe seed data. | [P-040](development.md#p-040) |
| P-041 | Accepted | Agents build/test the entire app locally; CI runs automated tests. No hosted preview/staging environment is required. | [P-041](development.md#p-041) |
| P-042 | Accepted | Local/CI external services use fakes or sandboxes: no real emails, charges, paid-service side effects or production writes. | [P-042](development.md#p-042) |
| P-043 | Accepted | Test against the actual chosen database engine, not a convenient substitute. | [P-043](development.md#p-043) |
| P-044 | Accepted | Shared dependency upgrades are reviewed and tested against affected apps; no silent production upgrades. | [P-044](development.md#p-044) |
| P-045 | Accepted | A release tag selects Pi or Railway—not an app configuration switch. | [P-045](delivery.md#p-045) |
| P-046 | Accepted | Deploy exact CI-tested immutable artifacts, not a production rebuild; test target-specific artifacts where needed. | [P-046](delivery.md#p-046) |
| P-047 | Accepted | Moving an app between Pi and Railway needs explicit migration, cutover and recovery approval. | [P-047](delivery.md#p-047) |
| P-048 | Accepted | Pi deployment uses a managed service pulling approved artifacts; no routine agent SSH. | [P-048](delivery.md#p-048) |
| P-049 | Accepted | One protected gateway with app subdomains; block origin bypass. | [P-049](delivery.md#p-049) |
| P-050 | Accepted | Default domain is <app-folder>.leo-figueiredo.com under a standard naming rule; other domains need Leo approval. | [P-050](delivery.md#p-050) |
| P-051 | Accepted | Health checks and operational visibility are mandatory on Pi and Railway. | [P-051](operations.md#p-051) |
| P-052 | Accepted | Both hosts require useful logs and resource limits. | [P-052](operations.md#p-052) |
| P-053 | Accepted | Use managed secrets; keep credentials and sensitive data out of source and exposed logs. | [P-053](operations.md#p-053) |
| P-054 | Accepted | Backups, tested restoration and recovery procedures on both hosts. | [P-054](operations.md#p-054) |
| P-055 | Accepted | Rust owns APIs, business logic and durable app jobs; lighter schedulers for isolated timed work; Airflow for coordinated multi-step workflows. Python may provide thin orchestration. | [P-055](workflows.md#p-055) |
| P-056 | Accepted | When state changes and pending work must happen together, use a proven transactional local queue or a cross-system outbox, with safe retries. | [P-056](workflows.md#p-056) |
| P-057 | Accepted | Repeat-safe operations, bounded transient retries, and status checks/manual review for ambiguous external outcomes. | [P-057](workflows.md#p-057) |
| P-058 | Accepted | Historical reruns require separate approval for consequential external actions. | [P-058](workflows.md#p-058) |
| P-059 | Accepted | App DAGs/tests stay app-local; small shared Python orchestration package; explicit platform cross-app workflows separate from deployment configuration. | [P-059](workflows.md#p-059) |
| P-060 | Accepted | Share Airflow for mutually trusted apps; separate deployments for security/reliability exceptions. Railway app projects stay separate. Airflow metadata has separate DB/credentials; tasks use scoped app APIs. | [P-060](workflows.md#p-060) |
| P-061 | Accepted | Per-workflow concurrency, resource pools where needed, timeouts, explicit overlap rules and historical-rerun limits; stronger isolation where necessary. | [P-061](workflows.md#p-061) |
| P-062 | Accepted | Each workflow has an owner, runtime/freshness expectations and safe recovery procedure. Actionable failures go to owner; important unresolved issues escalate through Chief of Staff to Leo. | [P-062](workflows.md#p-062) |
| P-063 | Accepted | Exchange small IDs/statuses; durable data remains app-owned behind authorized interfaces. Retain inputs/outputs long enough for required retries/reruns. | [P-063](workflows.md#p-063) |
| P-064 | Accepted | Record input references, data periods and workflow/processing versions. Distinguish original replay from new recalculation; report exact replay unavailable when necessary. | [P-064](workflows.md#p-064) |
| C-001 | Conditional | Generated Zod runtime validation is the proposed frontend direction, only after proving Rust-contract → TanStack Form integration. | [C-001](frontend.md#c-001) |
| C-002 | Conditional | Proposed test standard: Vitest for logic; Storybook real-browser shared UI tests; Playwright critical whole-app journeys against production builds. React Testing Library selectively, subject to repo compatibility. | [C-002](frontend.md#c-002) |

