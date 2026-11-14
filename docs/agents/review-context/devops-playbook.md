> Canonical decisions: [`docs/adr/README.md`](../../adr/README.md). New apps follow that index. Existing app commands and safety rules remain applicable. Leo approves every production release. Do not enable auto-merge or deploy without that approval.

# Delivery and DevOps Review Playbook

Review reference for `f0rge-delivery` and `f0rge-devops`. Read the [shared protocol](../protocol.md) and `docs/agents/rules/infra.md`, inspect the diff, and return concrete findings. Resolve exact primaries and independent reviewers with `node scripts/agents/agents.mjs route <repo-relative-path...>`. Build/CI work and runtime operations remain distinct; this retained playbook covers both for review, not duplicate ownership.

## Review coverage — not ownership routing

- `.github/**`, `**/railway*.toml`, Dockerfiles, compose and entrypoint files.
- Nx registration, root build/dependency configuration, `.dockerignore`, and `.gitignore`.
- Migration deployment compatibility and database roles; app behavior belongs to the backend reviewer.
- Domain, certificate, storage, and hosting changes.

## Checks

- Docker builds use the repository root when they consume shared libraries. A narrowed context must still include every dependency.
- Marrow `.dockerignore` files use an allowlist so unrelated apps, credentials, and local data stay outside the build context.
- Keep per-project Python locks; reject a root `uv.lock`.
- Marrow Railway configs use `preDeployCommand` for migrations. The command is configuration, not production approval. Runtime database credentials remain least-privilege; destructive migrations need a recovery plan.
- Role creation and production access changes require explicit authorization. Preserve migration-role and runtime-role separation.
- Reject committed deployment credentials, database passwords, and JWT secrets.
- Domain/certificate changes need an authorized operations task. New domains follow the canonical ADR naming/approval rules.
- CI status does not establish production approval, the running artifact, or successful app behavior. Verify the exact release and actual checks executed; preserve release holds.

## New environment variables

- Update the relevant `.env.example` and operations reference.
- Document missing-value behavior and test that it is safe.
- Change production variables only within the explicitly authorized release/operations scope.

## Verification

Use [the deploy manifest](../../../.github/deploy/manifest.yml) and app-local Railway/Coolify configuration to identify the affected services. Confirm current provider identity before an authorized operation. A queued deployment or HTTP 200 alone does not prove successful rollout; verify the running version and affected user journey.

Marrow production smoke targets are `https://api.marrow-health.com/api/v1/health` and `https://marrow-health.com/`. Firstout and DasKasas use their own projects and service checks; do not substitute Marrow health for a sibling app.
