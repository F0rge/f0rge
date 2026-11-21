# Delivery

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-045

- **Policy status:** Accepted (amended by Leo’s 20 November 2026 request)
- **Temporary ID:** P-045
- **Category:** Delivery
- **Decision:** There are no release tags. An App's Host (the Pi or Railway) is recorded once per deployable Project, in the deploy block of its `project.json`. All deployable Projects of one App share one Host. Release history is the App's GitHub environment.
- **Amendment (20 November 2026):** Leo requested removal of release tags. This replaces "a release tag selects Pi or Railway" and the Firstout release-tag grammar.
- **Implementation:** A Project is deployable when its `project.json` has `metadata.deploy` with a `host` (`railway` or `pi`) and a list of services; its App is its `scope:` tag. `.github/deploy/deployables.mjs` reads those blocks and fails when an App mixes Hosts. `cd.yml` runs each App's Release in the GitHub environment named after the App.
- **Approved exception:** None.

## P-046

- **Policy status:** Accepted (amended by Leo’s 20 November 2026 request)
- **Temporary ID:** P-046
- **Category:** Delivery
- **Decision:** Each Artifact is built once, in CI, and released by its commit tag; CD never builds. A Release contains all of an App's Artifacts from one commit. Artifacts are public unless a build needs a secret. A rollback puts each service back on the Artifact it ran before; it does not rebuild.
- **Amendment (20 November 2026):** Leo requested release by commit tag instead of digest, and public Artifacts. This replaces digest pull-back, release manifests and provenance checks.
- **Implementation:** For each affected App, the image job in `ci.yml` runs after the language jobs pass and builds every deployable Project, through the `image` Nx target (`.github/scripts/image.mjs`) (AMD64 for Railway, ARM64 for the Pi), starts each image, with a throwaway database when the Project needs one, and expects its health endpoint to answer. Pull requests build and check without pushing. `main` pushes `ghcr.io/f0rge/<nx project>:<commit sha>`.
- **Gate and limit:** A commit tag can in principle be overwritten; only `main` CI pushes. The manual path fails unless the Artifact exists for every Project of the App at that commit.
- **Approved exception:** None.

## P-047

- **Policy status:** Accepted
- **Temporary ID:** P-047
- **Category:** Delivery
- **Decision:** Moving an app between Pi and Railway needs explicit migration, cutover and recovery approval.
- **Implementation:** A Host move is a reviewed change to `host` in the Project's deploy block, made after Leo approves a plan for the database, files, secrets and domains. Nothing in the pipeline checks this; the reviewer does (P-004).
- **Approved exception:** None.

## P-048

- **Policy status:** Accepted (amended by Leo’s 20 November 2026 request)
- **Temporary ID:** P-048
- **Category:** Delivery
- **Decision:** Coolify is the Pi's managed puller: it pulls the commit-tagged Artifact and runs it. There is no custom release agent and no routine agent SSH for Releases.
- **Amendment (20 November 2026):** Leo requested Coolify as the puller and deletion of the custom release agent.
- **Implementation:** Each Pi service is a Coolify "Docker image" application named after its Nx project. `.github/deploy/deploy.mjs` sets its image tag and triggers a deployment through Coolify's API, using `COOLIFY_URL` and `COOLIFY_TOKEN` from the App's GitHub environment. Coolify's own Healthcheck stays off; the image's Docker `HEALTHCHECK` decides health (P-051).
- **Gate and limit:** On the Pi a bad Release causes downtime until the rollback completes.
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
- **Static evidence at `f155a2ba` (not normative, not a live check):** Custom-domain strings are already inventory in `apps/dk/tag-printer/AGENTS.md` and root `AGENTS.md` (for example `marrow-health.com`, `firstout.co.za`, and `tags.leo-figueiredo.com`). No domain-derivation checker exists. None of those names is an approved exception.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

