# Provider verification design — not an active release path

This is a proposal, not a verifier, an approval, or evidence that a provider
can supply the required facts. The [release hold](README.md) remains in force.
No provider change or deployment is performed by this document. P-006 requires
Leo's approval; P-045 selects the host by release tag; P-046 requires the
target-specific CI-tested artifact; P-051 requires meaningful health evidence.

## Proposed acceptance for a future release

A future provider adapter should fail closed unless it can obtain and retain
all of the following from authenticated, appropriately scoped sources:

1. **Approved target and artifact:** Leo's approval for the release request
   identifies the source commit, tested artifact digest and platform, and the
   exact provider, project, environment and service. The release tag maps to
   that host. A GitHub job result, user-supplied string, mutable image tag,
   local Docker image ID or archive checksum alone is not that proof. Bind the
   digest to the CI build and test results through verified provenance.
2. **Provider operation:** a provider-assigned deployment ID and terminal
   status identify the approved target and the operation that promoted the
   approved image without rebuilding. A configured image reference or
   successful queue response is not proof of the running image.
3. **Every serving replica:** an independent provider/runtime observation
   identifies all current serving replicas, each replica's deployment identity,
   platform and actual running image digest. All must match the approved
   artifact for that platform; a missing, old, unexpected or unknown replica
   fails verification. Distinguish an OCI index digest, selected platform
   manifest digest and image configuration ID; prove the mapping instead of
   comparing unlike values. If the provider cannot attest what each running
   replica uses, report verification unavailable and hold the release.
4. **Health and stability:** observe provider readiness and an app-specific
   health or safe synthetic journey against the same target and deployment.
   HTTP liveness alone does not establish the business journey or the image
   identity. Recheck the serving set after the health observations so a
   rollout, restart or replacement during verification cannot silently pass.
5. **Fresh evidence:** record source identity, collection time, deployment ID,
   approval and CI evidence references, and the observations in durable,
   access-controlled release records. Set and document maximum evidence age,
   acceptable clock skew and rollout-stability window before activation; no
   numeric targets are currently approved. Reject stale, future-dated,
   incomplete or inconsistent observations and re-observe after state changes.

The verifier must obtain facts from protected GitHub and provider interfaces,
not from an untrusted archive or the deployed application self-reporting its
identity. It must restrict credentials and avoid recording secrets or customer
data. Mismatches, ambiguous outcomes and verification failures require a hold
and an explicit recovery decision; do not automatically retry a consequential
release or imply a failed verification rolled back the service.

## Provider facts and gaps

- [Coolify's Docker Image documentation](https://coolify.io/docs/applications/deployments/docker-image)
  describes pulling an image by immutable SHA-256 digest without rebuilding.
  It describes inspecting deployment logs and health, but does not establish
  an independently authenticated digest observation for every running replica.
  The current service type, source and any alternate triggers still need a live
  audit and a tested, approved cutover.
- [Railway's deployment reference](https://docs.railway.com/deployments/reference)
  says an image-source deployment skips the build. That does not by itself
  prove immutable digest selection or a running-replica digest receipt; the
  relevant supported provider interface and its guarantees remain to be
  established. [Automatic image updates](https://docs.railway.com/deployments/image-auto-updates)
  can redeploy outside the approval path and must be controlled. Private
  registry access has [plan requirements](https://docs.railway.com/builds/private-registries)
  that need verification for the actual account.
- On 14 November 2026, a read-only Railway inspection found DasKasas
  `storefront` and `storefront-commerce` using the GitHub repository as their
  source, not the retained CI image. Commerce configured a pre-deploy Medusa
  migration/bootstrap and a photos volume. Both latest deployments reported
  success; that status was not evidence of a running image digest. Provider
  state may change; recheck it before any future cutover.

## Safe validation before activation

1. Use local, synthetic adapter fixtures for matching and mismatched target,
   digest, architecture, replica set, health and timestamps; include missing
   provider fields, stale evidence, rollout changes and provider failures.
   These tests establish parsing and decisions only, not provider guarantees.
2. Identify a supported authenticated source for the actual running digest
   and complete replica set on each provider. Independently review its trust,
   freshness and permissions; if unavailable, keep that provider blocked.
3. In a separately authorized isolated provider rehearsal, promote a retained
   target-specific tested artifact by digest and capture the provider receipt.
   Verify positive and negative cases, including a different digest, mixed or
   replaced replicas, unhealthy service, retries and unavailable evidence.
   No production service, secret, customer data or real charge is used. The
   current task authorizes no deployment, including this rehearsal.
4. Before an actual cutover, inventory and contain alternate automatic and
   manual provider paths, design a controlled migration for stateful services,
   verify backup restoration and recovery, and secure a separate requester and
   Leo's approval for the exact release. P-020 migration control and P-047
   destination-change approval apply where relevant. Recheck live state and
   complete independent delivery, security and operations review.

None of these steps currently creates a registry artifact, deploys it, verifies
an actual provider replica or proves approval/replay behavior.
