# Approval harness

`evaluate()` can permit a fixture. `execute()` does not call a provider while `EFFECTS_ENABLED` is false. A permit does not prove that Leo acted, and it does not prove a running image digest. There is no GitHub or Railway client in this module.

A permit requires a `SimulatedBoundary` instance and a `MemoryReplayStore` instance. A dict, a JSON object, or a source string is not that boundary. Caller fields named `receipt_source`, `approved`, or `consumed_approval_ids` are rejected. User ids must be real integers. The string `"38779415"` does not match the reviewer. `workflow_path` is required.

GitHub does not give an environment review a caller-chosen lifetime. This harness accepts `reviewed_at` and `expires_at` only when the window is at most 15 minutes and `now` falls inside it, with two minutes of future clock skew. A far-future expiry is denied. Replay uses the store object, not a list inside the receipt. The canonical digest includes the approver, the requester, the environment id, both timestamps, and each check attempt. Changing any of those without recomputing the digest is a deny.

GitHub's own review record, if one is later fetched, binds a workflow run and an environment. It does not bind an artifact sha256 or a Railway deployment id. Those equalities in this fixture are not that record. `live_human_approval_proved` and `provider_digest_proved` stay false.

## Permissions, not a grant

Do not grant these. Actions write is one repository-wide permission. It is not limited to one workflow. It includes dispatch, enable, disable, rerun, rerun-failed, cancel, and approving workflows from a fork pull request. That can re-enable Deploy workflow `253335437` and rerun old Deploy YAML, which injects whatever `COOLIFY_*` and `SMOKE_*` values are in Actions at job start, without a Secrets permission. Do not give any automation Actions write while that workflow is only `disabled_manually` and those historical runs still exist.

| Operation | Documented permission | Not the same as |
|---|---|---|
| Enable, disable, dispatch, rerun, cancel | Actions write | Administration write |
| Read approval history and pending deployments | Actions read | The approve call |
| `POST .../pending_deployments` for a required reviewer | Deployments write. The actor must still be a listed User or Team reviewer. An installation token is not user `38779415` | Contents read, or deployments read |
| Change environment reviewers, `prevent_self_review`, or branch policy | Administration write | Workflow enable |
| Environment secrets and variables | Environments permission | Reviewer settings |

An agent that can still act as user `38779415` can approve after some other starter begins the run. Hiding a requester key does not close that. Do not leave an owner or reviewer grant on an agent and call that safe. Leo remains the owner on a session automation cannot use at approval time. That break-glass is not a token mounted in the agent. No grant is revoked from here. Ops owns any later removal, after the consumer inventory. Unknown holders still block replacing secret values.

## What has to be true before any later grant

1. Ops keeps Deploy `253335437` disabled and the eight Railway push switches off. This module does not re-enable either.
2. Ops finishes the private recovery of the current Coolify values. Depot has retained the names `COOLIFY_BASE_URL`, `COOLIFY_WEBHOOK_DK_BACKEND`, and `COOLIFY_WEBHOOK_DK_FRONTEND`. The current five webhook names were not in that displayed list. `SMOKE_*` stay. Org secrets shared with this repository were an empty list. Values are not deleted or replaced here.
3. Every agent-held session of user `38779415` loses Deployments write and Administration write. Classic `repo` scope can approve and cannot be narrowed in place. Replacing such a token is a personal consent step on the existing account, not a new user and not an app install. Do it only after the uses of that token are listed.
4. Only then, and not in this pull request, a reviewed Administration write may set reviewer `38779415`, `prevent_self_review` true, `can_admins_bypass` false, and branch policy `main` on Marrow / production `19158860710`, Firstout / production `24561991680`, and storefront / production `23387956905`. A 403 stops that attempt. The other seven environments are not targets.

## Map

Railway project `d58a2884-d366-4230-9555-8b7bb4e42d4f` is named DasKasas and runs `storefront` and `storefront-commerce`. Those services bind only to GitHub environment `storefront / production` (`23387956905`). GitHub environment `DasKasas / production` (`24635670941`) is not that project and is not the dk Coolify apps. dk, buycycle, and environment-monitor stay unmapped. Same-build reuse is the only promotion kind this fixture can permit. An OCI digest is rejected. Live deployment ids from 2026-11-07 are builds of `ca3bc0fb` and are not an allow-list.

## CI line

This branch adds `test_approval_harness.py` to the unittest line in `ci.yml`. Pull request 907 adds `test_release_gate.py` on that same line. Landing both is a mechanical conflict. Integrate the line by hand later. Do not merge the branches to resolve it.
