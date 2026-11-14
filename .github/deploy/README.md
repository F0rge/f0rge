# Release hold and historical deploy manifest

The repository release entry points in this change are **inert**. The manual
`deploy.yml` and callable `deploy-reusable.yml` target the fixed GitHub
`production` environment without calling a provider, reading deployment
credentials or running a smoke against production. Both jobs set
`deployment: false`; the manual preparation job reports its limited scope and
the retired callable entry point fails. Neither is an approved release path. The repository's Nx CI
runs builds and tests; those results do not authorize a release. GitHub support
for `deployment: false` and the environment's effective protection have not
been verified by running this workflow.

On 14 November 2026, the repository `production` environment was configured
with Leo as the sole required reviewer, prevent self-review, no administrator
bypass and the `main` branch restriction. It has no environment secrets. Verify
settings and the exact selected environment again before activation. A separate
automation identity is needed for a release that Leo can approve independently;
an agent using Leo's account is not independent human approval.
The current environment allows `main` only and no tags; P-045's release-tag
grammar and corresponding protected tag allowlist need design before a
tag-triggered release.

`release_evidence.py` compares supplied candidate, artifact and check fields
offline. `test_release_evidence.py` exercises mismatches and the no-effect
workflow configuration. These fixtures do not retrieve trustworthy GitHub
approval or CI facts, prove a human acted, prevent real approval replay, verify
a provider's running digest or authorize a release.

Expiry and replay enforcement are not implemented here. Before activation,
test that an expired review is rejected and that reusing the same approved
commit/digest/target is handled safely after a restart or with a different
approval ID. Verify whether a rerun requires fresh GitHub approval. No
process-local fixture is proof of durable replay protection.

Before a future release path is enabled, build and test a target-specific image
once, retain its immutable digest, obtain independent GitHub approval for that
commit/digest/target, promote that same image without rebuilding and verify the
running digest and health. Test reruns, mismatches and recovery in an isolated
environment. Audit and control Railway, Coolify, manual, historical rerun and
other alternate provider paths; their current live state is not established by
this change. Do not put deployment credentials into repository-level secrets or
activate a provider trigger merely to make this hold pass. Every production
release still needs Leo's explicit approval.

## Historical configuration — not an active release path

The following inventory and commands document the former source-based path;
they do not describe a runnable deployment workflow in this change. Do not add
secrets or use the legacy webhooks to bypass the release hold. Retained code
and tests support investigation, not production authorization.

The manifest records the legacy mapping of Nx projects to deployment targets.
The historical orchestrator intersected it with `nx affected`, then delegated
to Railway smoke or Coolify executors; those jobs are no longer present in the
proposed workflows.

Committed configuration describes **Railway deployment plus Actions smoke** for Marrow. Check current provider triggers before an authorized release; this file does not enable them or grant production approval.
dk tag-printer, buycycle, and environment-monitor run on Coolify (Pi). Firstout is a **separate Railway
project** (not Marrow),
**`main` only**, in Railway environment `production`
(`9f7b0c34-bd95-442b-b746-a9791dcc2895`). Hosts: `firstout.co.za` /
`api.firstout.co.za` (Swagger at `/docs`).

DasKasas storefront is a separate Railway project (`d58a2884-d366-4230-9555-8b7bb4e42d4f`),
production environment `d73ff2d5-816d-4bc8-85b4-71a85b0398fa`, with services
`storefront` and `storefront-commerce`. Its `apps/storefront/` Railway configs are
outside this manifest; verify both services separately for an approved release.

## Historical webhook secret inventory

The former workflow used `COOLIFY_BASE_URL` and per-component
`COOLIFY_WEBHOOK_*` values, with optional `SMOKE_EMAIL` and `SMOKE_PASSWORD`
for Railway smoke. Their location, current consumers and provider permissions
require a separate live audit. The new inert workflows neither receive nor use
these values. Any future production credentials must be restricted to an
approved protected environment and unavailable to ungated jobs.

## Historical Coolify monorepo settings (per app)

| Field | dk tag printer | environment-monitor |
|-------|----------------|---------------------|
| Repo | `F0rge/f0rge` | `F0rge/f0rge` |
| Branch | `main` | `main` |
| Base directory | `/` | `apps/environment-monitor/backend` or `.../frontend` |
| Dockerfile | `apps/dk/tag-printer/backend/Dockerfile` or `.../frontend/Dockerfile` | `Dockerfile` (relative to that base) |
| Watch paths | `apps/dk/tag-printer/backend/**` or `.../frontend/**` | `apps/environment-monitor/backend/**` or `.../frontend/**` |
| Frontend build-time env | `NEXT_PUBLIC_API_URL=https://tags-api.leo-figueiredo.com` | keep existing `BACKEND_URL` |
| Backend runtime env | `CORS_ORIGINS=https://tags.leo-figueiredo.com` | keep existing `PYTHONUNBUFFERED` (both apps) |

The former webhook supplied a Git diff and signed it with a component-specific
secret. It classified queued, watch-path-skipped and rejected responses.
These details describe the retired source-building path, not an approval or
immutable artifact mechanism. Retained payload and planner tests document the
legacy behavior without contacting a provider.

See also [manifest.yml](manifest.yml) and [plan_deploy.py](plan_deploy.py).

## Historical workflow selection

The former `workflow_run` deployment used the default branch's workflow files.
Historical reruns can use historical workflow definitions, so removing a trigger
from a new revision does not prove those paths are closed. Verify their controls
before activating any release mechanism.
