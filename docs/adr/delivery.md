# Delivery

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-045

- **Policy status:** Accepted
- **Temporary ID:** P-045
- **Category:** Delivery
- **Decision:** A release tag selects Pi or Railway—not an app configuration switch. For Firstout continuous deployment, the trusted pipeline automatically creates `release/firstout/railway/<source SHA>` after testing; the tag selects the fixed Firstout Railway target. No additional per-release approval is required within the Firstout scope of P-006. Other apps retain their existing approval rule.
- **Enforcement and remaining setup:** `.github/workflows/cd-firstout.yml` accepts only successful CI runs originating from this repository's main pushes. `.github/scripts/firstout-cd.py` verifies source checks and reviewed-PR provenance, tests target images before publication and creates a nonmoving source tag. Tag protection and the scoped `firstout-production` environment/credentials must be configured during activation. The runtime controller rechecks exact tag/source/target. The PR implements the path; it does not claim those live controls were activated.
- **Gate and limit:** Release policy: immutable tag/commit/target audit. Firstout uses the exact grammar above and rejects ambiguous or moved refs; other apps' tag grammar remains to design.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Manifest branches: [main] and a static target field per component. workflow_dispatch environment choices are only main.
- **Implementation:** Firstout's automatic tag/artifact path is implemented in this PR, pending scoped credential/environment/tag-rule setup and provider rehearsal. Other apps retain their release holds. Historical static evidence below does not establish live activation.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-046

- **Policy status:** Accepted
- **Temporary ID:** P-046
- **Category:** Delivery
- **Decision:** Deploy exact CI-tested immutable artifacts, not a production rebuild; test target-specific artifacts where needed. Firstout releases a coordinated backend/frontend image pair, database schema/policy metadata and asset hashes bound to one source SHA. Rollback selects the retained previous working images; it does not rebuild an old branch.
- **Enforcement and remaining setup:** Firstout's CD workflow builds each Linux/AMD64 image once, runs offline image checks with disposable PostgreSQL, tests the retained previous backend against the new schema and candidate-written data, publishes and pulls back by digest, and retains the release manifest. The controller checks GitHub workflow/attempt provenance and actual provider image digests/serving instances before and after rollout or recovery. Public frontend health/assets and synthetic backend HTTP checks are covered; real Clerk/browser journeys and live provider rehearsal remain activation evidence. Other apps' artifact promotion remains unchanged.
- **Gate and limit:** Build + release: artifact/test/provenance chain for Pi ARM64 and Railway target as applicable. A shared tag alone is not artifact identity.
- **Static evidence at `f155a2ba` (not normative, not a live check):** CI builds artifacts inside the test job and discards them. Workflow files are configured to call Railway smoke or Coolify webhooks. A live rebuild was not observed. Health URLs are checked after the fact for some components.
- **Implementation:** Firstout's coordinated immutable-image workflow and controller are implemented in this PR; live publication, provider rollout and recovery require activation/rehearsal evidence. Other apps' promotion remains held. Local tests establish only the checks actually exercised.
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
- **Static evidence at `f155a2ba` (not normative, not a live check):** Custom-domain strings are already inventory in `.github/deploy/manifest.yml`, `apps/dk/tag-printer/AGENTS.md`, and root `AGENTS.md` (for example `marrow-health.com`, `firstout.co.za`, and `tags.leo-figueiredo.com`). No domain-derivation checker exists. None of those names is an approved exception.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

