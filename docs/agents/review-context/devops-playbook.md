> Canonical decisions: [`docs/adr/README.md`](../../adr/README.md). Follow [P-005](../../adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../../adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

# Delivery and DevOps Review Playbook

Review reference for `f0rge-delivery` and `f0rge-devops`. Read the [shared protocol](../protocol.md) and `docs/agents/rules/infra.md`, inspect the diff, and return concrete findings. Resolve exact primaries and independent reviewers with `node scripts/agents/agents.mjs route <repo-relative-path...>`. Build/CI work and runtime operations remain distinct; this retained playbook covers both for review, not duplicate ownership.

## Review coverage — not ownership routing

- `.github/**`, deploy blocks in `project.json`, Dockerfiles, compose and entrypoint files.
- Nx registration, root build/dependency configuration, `.dockerignore`, and `.gitignore`.
- Migration deployment compatibility and database roles; app behavior belongs to the backend reviewer.
- Domain, certificate, storage, and hosting changes.

## Checks

- Docker builds use the repository root when they consume shared libraries. A narrowed context must still include every dependency.
- Marrow `.dockerignore` files use an allowlist so unrelated apps, credentials, and local data stay outside the build context.
- Keep per-project Python locks; reject a root `uv.lock`.
- Migrations are the `preDeployCommand` in a deploy block and run unattended on every Release (P-020). Each must work with the previous commit's code: the automatic rollback does not downgrade the schema. Runtime database credentials remain least-privilege; a destructive migration names its recovery plan in the PR.
- Role creation and production access changes require explicit authorization. Preserve migration-role and runtime-role separation.
- Reject committed deployment credentials, database passwords, and JWT secrets.
- Domain/certificate changes need an authorized operations task. New domains follow the canonical ADR naming/approval rules.
- A merge releases. Review a deploy-block, Dockerfile or workflow change as a production change: service names must match the Host.

## New environment variables

- Update the relevant `.env.example` and operations reference.
- Document missing-value behavior and test that it is safe.
- Change production variables only within the explicitly authorized release/operations scope.

## Verification

`node .github/deploy/deployables.mjs` lists each App's Host, Projects and services. The App's GitHub environment shows its Release history. Confirm current provider identity before an authorized operation outside the pipeline.

Marrow production smoke targets are `https://api.marrow-health.com/api/v1/health` and `https://marrow-health.com/`. Firstout and DasKasas use their own projects and service checks; do not substitute Marrow health for a sibling app.
