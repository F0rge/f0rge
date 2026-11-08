# Backend

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-011

- **Policy status:** Accepted
- **Temporary ID:** P-011
- **Category:** Backend
- **Decision:** Rust for new backends; transition existing Python/FastAPI backends gradually.
- **Proposed enforcement (not installed):** New-app template and manifest checks require Rust backend targets; migration inventory tracks legacy APIs and compatibility tests.
- **Gate and limit:** Static + test: Cargo build/test and exception-aware stack audit. Python thin Airflow orchestration is explicitly allowed.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None that reject a new Python HTTP service.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-012

- **Policy status:** Accepted
- **Temporary ID:** P-012
- **Category:** Backend
- **Decision:** Actix Web is the default Rust HTTP framework, not Axum.
- **Proposed enforcement (not installed):** Cargo metadata dependency-policy check validates app HTTP entrypoints use the approved framework; reusable Actix bootstrap template has an HTTP smoke test.
- **Gate and limit:** Static + integration: framework/dependency report. Do not ban unrelated transitive crates merely because another framework uses them.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-013

- **Policy status:** Accepted
- **Temporary ID:** P-013
- **Category:** Backend
- **Decision:** Diesel is the PostgreSQL ORM; asynchronous integration is the planned direction.
- **Proposed enforcement (not installed):** Approved Diesel adapter template; Cargo dependency/feature inspection and PostgreSQL integration tests prove pooling, transactions and async behavior before adoption.
- **Gate and limit:** Static + integration: Diesel selection is agreed; exact async adapter/version and queue transaction compatibility need proof. SQLx/SeaORM are not selected defaults.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None for Diesel. Migration tests use SQLAlchemy and Alembic.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-014

- **Policy status:** Accepted
- **Temporary ID:** P-014
- **Category:** Backend
- **Decision:** Layer each app into handlers, business services and database access; add domain modules where useful. No microservices by default; API and app jobs reuse business services.
- **Proposed enforcement (not installed):** Crate/module boundary policy, Rust visibility and AST/dependency checks disallow handler-to-storage shortcuts and job/API duplication; service tests drive both entrypoints.
- **Gate and limit:** Static + test + review: dependency graph and shared-service behavior tests. Folder names alone cannot prove separation or absence of duplicated logic.
- **Static evidence at `f155a2ba` (not normative, not a live check):** A written Marrow convention. No AST or Cargo dependency check. A ripgrep for line-start if under apps/marrow/backend/app/routers returned no files; that pattern does not prove the layering rule.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-015

- **Policy status:** Accepted
- **Temporary ID:** P-015
- **Category:** Backend
- **Decision:** Small shared Rust plumbing libraries; app-specific business rules, database models and migrations stay app-local.
- **Proposed enforcement (not installed):** Cargo graph rules prevent shared infrastructure crates importing app crates; ownership checks flag app models/migrations in shared packages; reviewer checks abstraction size.
- **Gate and limit:** Static + human: resolved dependency graph and model/migration ownership report. Shared mechanism is not a shared business-model mega-library.
- **Static evidence at `f155a2ba` (not normative, not a live check):** CI grep rejects Python imports of apps from libs/backend and TypeScript imports of apps from libs. Nx boundary tags cover shared, marrow, dk, firstout, and vellano only.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

