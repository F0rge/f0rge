# Delivery

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-045

- **Policy status:** Accepted
- **Temporary ID:** P-045
- **Category:** Delivery
- **Decision:** A release tag selects Pi or Railway—not an app configuration switch.
- **Proposed enforcement (not installed):** Protected tag parser maps approved release to app/target; validate allowed target and build evidence. Optional app metadata may describe capabilities, never override the tag.
- **Gate and limit:** Release policy: immutable tag/commit/target audit. Exact tag grammar remains to design; reject ambiguous or moved refs.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Manifest branches: [main] and a static target field per component. workflow_dispatch environment choices are only main.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-046

- **Policy status:** Accepted
- **Temporary ID:** P-046
- **Category:** Delivery
- **Decision:** Deploy exact CI-tested immutable artifacts, not a production rebuild; test target-specific artifacts where needed.
- **Proposed enforcement (not installed):** Build once per supported target, test that artifact, record digest/commit/architecture and promote by digest. Verify deployed receipt against approval.
- **Gate and limit:** Build + release: artifact/test/provenance chain for Pi ARM64 and Railway target as applicable. A shared tag alone is not artifact identity.
- **Static evidence at `f155a2ba` (not normative, not a live check):** CI builds artifacts inside the test job and discards them. Workflow files are configured to call Railway smoke or Coolify webhooks. A live rebuild was not observed. Health URLs are checked after the fact for some components.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-047

- **Policy status:** Accepted
- **Temporary ID:** P-047
- **Category:** Delivery
- **Decision:** Moving an app between Pi and Railway needs explicit migration, cutover and recovery approval.
- **Proposed enforcement (not installed):** Release preflight compares current destination with tag target; changed destination requires approved plan covering DB/files/secrets/domains, compatibility, cutover and rollback/recovery.
- **Gate and limit:** Human + release: destination-change approval and restore/cutover evidence. Changing a tag must not silently move stateful data.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Human review of manifest edits, only if branch review actually happens. P-005 shows reviews are not required.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-048

- **Policy status:** Accepted
- **Temporary ID:** P-048
- **Category:** Delivery
- **Decision:** Pi deployment uses a managed service pulling approved artifacts; no routine agent SSH.
- **Proposed enforcement (not installed):** Scoped pull/deploy identity verifies approved artifact; restrict deployment privileges and maintain receipt/health checks. Agents submit changes through the platform pipeline.
- **Gate and limit:** Infra + release: pull-service configuration and deployment audit. Tool selection/access need assessment; this Page changes no Pi configuration.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Coolify webhook response is classified. Manifest comments say GitHub runners cannot reach the Pi, so buycycle and environment-monitor have no health URL.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-049

- **Policy status:** Accepted
- **Temporary ID:** P-049
- **Category:** Delivery
- **Decision:** One protected gateway with app subdomains; block origin bypass.
- **Proposed enforcement (not installed):** Ingress policy and origin restrictions; test authenticated gateway success, anonymous denial and direct-origin/spoofed-header rejection.
- **Gate and limit:** Infra + runtime: route/access tests on both hosts. A DNS alias alone does not secure the origin or solve connectivity.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None for anonymous denial or direct-origin rejection.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-050

- **Policy status:** Accepted
- **Temporary ID:** P-050
- **Category:** Delivery
- **Decision:** Default domain is <app-folder>.leo-figueiredo.com under a standard naming rule; other domains need Leo approval.
- **Proposed enforcement (not installed):** Domain derivation validator checks normalization/collisions; release policy compares requested domains with default or approved exception.
- **Gate and limit:** Static + infra + human: derived-domain and approval record. Existing custom domains must be inventoried, not removed automatically.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

