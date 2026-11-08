# Workflows

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-055

- **Policy status:** Accepted
- **Temporary ID:** P-055
- **Category:** Workflows
- **Decision:** Rust owns APIs, business logic and durable app jobs; lighter schedulers for isolated timed work; Airflow for coordinated multi-step workflows. Python may provide thin orchestration.
- **Proposed enforcement (not installed):** Workflow classification in brief; shared job/API service tests; boundary review flags Python business-rule duplication or inappropriate Airflow use for request serving/streaming.
- **Gate and limit:** Review + dependency/behavior tests: classification and responsibility map. No job library selected; not every background task becomes a DAG.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Ruff lint of apps/airflow/dags. No classification schema and no check that Python DAGs avoid business rules.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-056

- **Policy status:** Accepted
- **Temporary ID:** P-056
- **Category:** Workflows
- **Decision:** When state changes and pending work must happen together, use a proven transactional local queue or a cross-system outbox, with safe retries.
- **Proposed enforcement (not installed):** Fault-injection tests fail before/after commit and dispatch; prove rollback and eventual delivery without lost work; verify selected queue participates in the Diesel transaction.
- **Gate and limit:** Integration: crash/restart and transaction evidence. No queue product selected; cannot assume a library is transaction-compatible or claim exactly-once external effects.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Firstout outbox tests exist and were not executed. No crash-injection gate and no platform queue.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-057

- **Policy status:** Accepted
- **Temporary ID:** P-057
- **Category:** Workflows
- **Decision:** Repeat-safe operations, bounded transient retries, and status checks/manual review for ambiguous external outcomes.
- **Proposed enforcement (not installed):** Idempotency keys and durable outcome/status records; simulate duplicate delivery, timeout-after-success and restart; classify permanent vs transient failure and cap retry/backoff.
- **Gate and limit:** Integration + runtime: duplicate/crash tests and ambiguous-outcome review state. Retrying a timeout must not blindly repeat a charge/message.
- **Static evidence at `f155a2ba` (not normative, not a live check):** App-local tests. No shared retry cap checker.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-058

- **Policy status:** Accepted
- **Temporary ID:** P-058
- **Category:** Workflows
- **Decision:** Historical reruns require separate approval for consequential external actions.
- **Proposed enforcement (not installed):** Replay mode separates computation from side-effect execution; app-owned approval checks bind action, scope and replay run; negative tests prove reruns cannot bypass approval.
- **Gate and limit:** Human + runtime: action approval/audit and denied replay-side-effect tests. A general rerun request or old approval is not new authorization.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None identified.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-059

- **Policy status:** Accepted
- **Temporary ID:** P-059
- **Category:** Workflows
- **Decision:** App DAGs/tests stay app-local; small shared Python orchestration package; explicit platform cross-app workflows separate from deployment configuration.
- **Proposed enforcement (not installed):** Proposed bundle/package manifest and ownership checks; import/parse CI with no network/DB calls, stable namespaced IDs, absolute imports and pinned helper dependencies; publish tested versioned bundles/artifacts.
- **Gate and limit:** Static + parse + release: layout/import/version evidence. Exact paths, bundle backend and packaging remain to design; naming/parse details here are proposed enforcement conventions, not separate historical decisions.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Ruff on apps/airflow/dags. No import parse that forbids network or database calls at import time. No versioned bundle artifact beyond git refs.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-060

- **Policy status:** Accepted
- **Temporary ID:** P-060
- **Category:** Workflows
- **Decision:** Share Airflow for mutually trusted apps; separate deployments for security/reliability exceptions. Railway app projects stay separate. Airflow metadata has separate DB/credentials; tasks use scoped app APIs.
- **Proposed enforcement (not installed):** Trust-boundary deployment review; separate metadata ownership/grants; app/org/action-scoped automation auth and negative API tests. Record approved isolation exceptions.
- **Gate and limit:** Infra + security + human: topology/credential map. Namespaces, pools, queues and UI RBAC are not hard tenant isolation; shared DAG authors must be trusted.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Documentation and compose. No negative test that a DAG credential cannot read another app's database. No isolation-exception record.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-061

- **Policy status:** Accepted
- **Temporary ID:** P-061
- **Category:** Workflows
- **Decision:** Per-workflow concurrency, resource pools where needed, timeouts, explicit overlap rules and historical-rerun limits; stronger isolation where necessary.
- **Proposed enforcement (not installed):** Workflow policy schema requires values or justified inapplicability; parse configuration checks plus load/overlap/backfill tests and runtime saturation monitoring.
- **Gate and limit:** Static + test + runtime: workload policy and limit evidence. Actual values follow assessment; do not present invented limits as approved.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None that parse a workflow policy file.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-062

- **Policy status:** Accepted
- **Temporary ID:** P-062
- **Category:** Workflows
- **Decision:** Each workflow has an owner, runtime/freshness expectations and safe recovery procedure. Actionable failures go to owner; important unresolved issues escalate through Chief of Staff to Leo.
- **Proposed enforcement (not installed):** Workflow ownership/runbook schema; monitor runtime and data freshness; synthetic failure and escalation-routing tests with sandbox notifications.
- **Gate and limit:** Config + runtime + human: owner/runbook coverage and alert-routing evidence. This is policy, not an installed alerting integration or permission to send notifications now.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-063

- **Policy status:** Accepted
- **Temporary ID:** P-063
- **Category:** Workflows
- **Decision:** Exchange small IDs/statuses; durable data remains app-owned behind authorized interfaces. Retain inputs/outputs long enough for required retries/reruns.
- **Proposed enforcement (not installed):** Typed job/XCom payload limits and reference schemas; authorization tests for storage reads; retention policy validated against replay window; missing-input tests fail clearly.
- **Gate and limit:** Contract + integration + runtime: payload/access/retention evidence. No large datasets or secrets in XCom/logs; references must not become bearer-secret leaks.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None for payload size, XCom content, or retention versus replay window.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-064

- **Policy status:** Accepted
- **Temporary ID:** P-064
- **Category:** Workflows
- **Decision:** Record input references, data periods and workflow/processing versions. Distinguish original replay from new recalculation; report exact replay unavailable when necessary.
- **Proposed enforcement (not installed):** Run provenance schema and version pinning; replay fixtures verify original inputs/rules and recalculation labeling; explicitly test missing historical code/data/dependencies.
- **Gate and limit:** Integration + audit: replay manifest and reproducibility result. DAG bundle pinning does not pin separately deployed Rust APIs, input data or environment dependencies.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

