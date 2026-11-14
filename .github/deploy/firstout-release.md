# Firstout frontend: tested image and operator release

This is the Firstout frontend path only. All other repository release holds
remain in force. No API, database, credentials, domains or resource settings
are changed by the promotion helper. The former GitHub deploy workflows remain
inert; the new artifact workflow builds and publishes but never deploys.

The operator needs Leo's explicit approval for the selected release. A chat
approval can provide that consent for an operator-run release. A string passed
to `--approval-reference` records where consent was given; it does not prove a
human identity or create approval. The local helper is not a GitHub environment
approval gate, and must not approve a protected environment as Leo. Future
release automation with independent human approval remains separate work.

## Target and prerequisites

- Repository: `F0rge/f0rge`, source reachable from `main` with successful `ci` and
  `playwright smoke` checks from the main GitHub Actions workflows.
- Tag: `release/firstout-frontend/railway/YYYYMMDDTHHMMSSZ`. Repository tag rules
  must prevent updating/deleting matching tags; verify the effective rule before
  creating one. The workflow and helper both resolve the tag to the source SHA.
- Image: `ghcr.io/f0rge/firstout-frontend@sha256:<manifest digest>`, public pull.
  The source repository is public; images must contain no credentials or user data.
- Target architecture: `linux/amd64`, a single OCI/Docker image manifest. Buildx
  provenance/SBOM index generation is disabled in this initial path; no signed
  supply-chain attestation is claimed.
- Railway project `c76d8df1-d839-454c-a94a-79b930deaf38`, production environment
  `9f7b0c34-bd95-442b-b746-a9791dcc2895`, frontend service
  `10838be1-7a37-4dfc-810a-8805d040d5d7`. One running replica is expected.
- Existing authenticated `gh` and `railway` CLIs on the operator machine. No
  Railway credential is stored in GitHub by this path.
- Repository Actions variables `FIRSTOUT_API_URL`,
  `FIRSTOUT_CLERK_PUBLISHABLE_KEY`, and `FIRSTOUT_TENANT_SUBDOMAINS_ENABLED` contain
  only the current public frontend build configuration. Runtime Clerk and proxy
  secrets remain on the existing Railway service.

## Build once and retain evidence

1. Select the exact approved source SHA on `main`; create its immutable release
   tag. Record both. Do not move or reuse a tag after a failure.
2. Run **Firstout tested release image** (`release-firstout.yml`) from `main`, with
   the tag and full source SHA. It runs the app's lint/typecheck/unit tests,
   builds one target image, and exercises its health/host/static-page behavior
   with container networking disabled.
3. The workflow publishes the tested image, pulls the immutable reference back,
   checks the platform, revision label and image ID, then uploads
   `firstout-release-evidence/firstout-release.json`. Publication is not release
   approval. Check the package is publicly pullable before provider rehearsal.
4. Wait for the artifact workflow to finish successfully. Retain its run/attempt,
   artifact ID, archive SHA-256, image manifest digest, source and workflow SHA.

The operator helper retrieves the archive through authenticated GitHub APIs;
it checks the API's artifact archive digest before parsing the manifest. It
checks the workflow identity, exact run/attempt, image/target/architecture, tag
and main ancestry, plus the source SHA's successful main CI and E2E workflows.
A local file containing `tested: true` is never accepted as release evidence.

```bash
python3 .github/deploy/firstout_release.py evidence \
  --run-id <successful-artifact-run-id> --output /private/release/evidence.json
python3 .github/deploy/firstout_release.py inspect \
  --output /private/release/before.json
```

Use an operator-owned, private directory outside the public repository. The
helper writes mode-0600 files and redacts registry credentials. Pending staged
changes are represented only as a boolean; their values are not retained.

## Rehearse before the first production promotion

Create an isolated temporary empty service in the same Firstout project, with
an explicit `firstout-release-rehearsal-` name. Do not duplicate an environment,
reference production variables, attach a volume/database, or give it Clerk or
proxy secrets. Set only the startup/port/health/resource configuration necessary
to run the public tested image. Keep image auto-updates disabled.

Deploy that same pinned image with the supported Railway source-image path.
Wait for `SUCCESS`; read the actual deployment's `meta.imageDigest`, and
`serviceInstance.activeDeployments` with each deployment's `instances` IDs and
statuses. Confirm the provider digest equals the registry's single-platform
manifest digest, one active deployment contains the expected running replica,
and the health/static behavior works. Read the serving set again after health.
Record this independent provider receipt. The helper's pure verification
functions can be reused with the temporary service ID for this rehearsal;
the production CLI target cannot be overridden.

Unit fixtures separately exercise mismatched digests, wrong target/run/attempt,
failed/spoofed CI, moved tags, overlap/missing/unhealthy/replaced replicas,
bad health and lost submission responses. Do not intentionally replace
production with a bad artifact to test these cases.

Remove the task-owned rehearsal service after retaining its receipt. A successful
rehearsal does not authorize production; use the already recorded approval for
the selected release.

## Promote only the verified image

Before merging the pipeline or submitting a release, inspect the live Firstout
project's deployment-trigger inventory. Retained `source.repo/main` values do
not establish whether auto-deploy is active. On 14 November 2026 the authenticated
project query returned no deployment triggers, with no further page. Recheck;
the helper fails if triggers appear, so unrelated API deployments cannot be
silently introduced by this release path.

```bash
python3 .github/deploy/firstout_release.py promote \
  --run-id <successful-artifact-run-id> \
  --approval-reference '<reference to Leo’s explicit release consent>' \
  --receipt /private/release/promotion.json
```

This exclusively creates a durable journal before submitting one
`environmentPatchCommit`. The patch affects only the fixed frontend service's
source: pinned image, Git source/branch/commit cleared, image updates disabled.
Existing runtime settings and secrets are preserved. It captures the prior
healthy rollback-capable deployment ID, provider image digest and redacted
configuration. An environment with pending changes is rejected.

The command returns a provider workflow ID. Observe the resulting frontend
deployment through `list-deployments` or the authenticated API; wait for that
specific deployment to become `SUCCESS`. Do not treat submission as success.
If submission loses its response, the journal says
`submission_outcome_unknown`: inspect current source/latest deployment and
provider workflow before taking any further action. Do not rerun `promote`
with a fresh journal to retry an ambiguous action. An exclusive journal and
already-selected-image guard reduce accidental replay; they are not a
platform-wide durable authorization/replay system.

```bash
python3 .github/deploy/firstout_release.py verify \
  --receipt /private/release/promotion.json --deployment-id <deployment-id>
```

Verification retrieves trusted artifact evidence again, checks the pinned source
and disabled updates, unchanged build/runtime/networking configuration, exactly
one active successful deployment, its provider `meta.imageDigest`, and its one
`RUNNING` instance. It requests the exact production `/healthz` URL with
`no-store` and `{"status":"ok"}`, then repeats the provider observation and
requires unchanged serving instance IDs. Retain the resulting JSON receipt.
Drive the approved UI journey against the deployed app as a separate release
check; health alone does not establish the requested business behavior.

The provider receipt maps Railway's deployment-owned image digest to every
instance listed under that deployment. Railway does not expose a separate
per-instance digest field in the inspected API. This is provider identity
evidence, not independent attestation of every running executable or a claim
that a configured source URL alone proves the running image.

## Recovery

Recover if the exact provider digest, serving set, health or approved UI fails
verification. Preserve the failed deployment and receipt before recovery. The
preflight captures the previous deployment while `canRollback` is true; recheck
that property immediately before using the supported rollback mutation:

```bash
railway api 'mutation($id:String!){deploymentRollback(id:$id)}' \
  --variables '{"id":"<before.active_deployments[0].id>"}'
```

This selects the previous retained deployment rather than rebuilding an old
Git ref or deploying the current `main`. Wait for the resulting serving
deployment and check that its provider digest matches the captured previous
digest, all expected replicas run, and production health/UI recover. Recheck
source configuration and deployment triggers after rollback; do not reconnect
mutable Git source or enable automatic updates merely to restore the old UI.
No rollback is claimed until those observations pass. If the old deployment is
no longer rollback-capable, stop and prepare a separately verified retained
artifact recovery instead of rebuilding implicitly.

## Limits retained

The manual operator uses existing credentials and the user's explicit consent;
the dormant GitHub production environment does not control that CLI session.
Separate requester identity, automatic approval expiry/replay controls,
signed provenance and a generalized multi-app release service are not implemented
by this Firstout-only path. Existing historical workflow/credential risks for
other apps remain under their release holds. No new production secret or
permanent automatic-release permission is introduced here.
