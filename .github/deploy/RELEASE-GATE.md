# Release gate

This file says what the repository change prepares and what it does not enforce. It is not an approval mechanism.

## What this change prepares

`release_gate.py` always returns `deny`. The last reason is `external_approval_binding_not_configured`. A merge, tag, green CI run, manual dispatch, rerun, pull-request sentence, or value in this repository is not an approval. `deny_from_env` prints that denial and returns 1. It reads only the environment keys the workflows set. It does not fill in a successful CI result when those keys are absent.

`test_release_gate.py` checks that function and those env shapes. A passing test means the function returned `deny`. It does not mean a release was approved, that a person was bound to a digest, or that the workflow fetched an immutable artifact. The synthetic filled record uses `event_name` `not-a-github-event` so the only reason is the missing binding. The workflow tests use the events these files actually emit: `workflow_run` and `workflow_dispatch`. `workflow_dispatch_rerun` is not a GitHub event and is not treated as one. A rerun keeps the original event name; `run_attempt` greater than 1 is recorded and still denies.

`.github/workflows/release-gate.yml` is `workflow_dispatch` only, `contents: read`, no secrets. The Python process exits 1. It does not read a CI run, so it does not claim one succeeded.

`.github/workflows/deploy.yml` still starts on `workflow_run` after CI and on `workflow_dispatch`. The guard can still run. The job that used to call `deploy-reusable.yml` now calls `deny_from_env` and exits 1. It passes `github.event.workflow_run.conclusion`, `.event`, `.head_sha`, `.head_branch`, and `.path` through when that event has them. Those fields are the triggering CI record GitHub attached. They are not a digest and they do not authorize a rollout. `workflow_dispatch` leaves them empty. The component value is `auto`, `all`, `api`, `mcp`, or `frontend`, which are not in `KNOWN_TARGETS`. That list is not the live service inventory and it does not authorize anything.

## Callers of the reusable workflows in this tree

Searched `uses:` of the local reusable workflows:

| File | Calls | Trigger |
|---|---|---|
| `.github/workflows/deploy.yml` on `main` before this change | `.github/workflows/deploy-reusable.yml`, and passes `COOLIFY_*` and `SMOKE_*` | `workflow_run` after CI, and `workflow_dispatch` |
| `.github/workflows/deploy.yml` in this change | nothing reusable | same triggers; the job exits 1 |
| `.github/workflows/deploy-reusable.yml` | `.github/workflows/railway-smoke-reusable.yml` | `workflow_call` only |
| `.github/workflows/railway-smoke-reusable.yml` | no further workflow | `workflow_call` only |

No other file in the tree calls `deploy-reusable.yml`. Both reusable files remain. A later workflow on the default branch can call them and pass secrets. `on: workflow_call` does not add a button that runs them by themselves. `gh run list` for those workflow ids returned an empty page; executions show up on the caller.

## Not closed

- Until this file is the `deploy.yml` GitHub runs, `main` still has the caller above. This pull request is not that merge.
- Re-running a historical successful Deploy run uses that run's workflow file. Run `40894098022` (2026-10-29, head `f155a2ba0a320f2c43da02cf6f8a94253ed1f93e`, https://github.com/F0rge/f0rge/actions/runs/40894098022) succeeded and called the reusable workflow. Re-running it was not tested and is not blocked by this change.
- `workflow_dispatch` of Deploy on `main` before this change is merged still uses the old file.
- Coolify git auto-deploy, as distinct from the webhook the old workflow called, was not read. Unknown is not the same as off.
- Pi copy and pull routes were not read. Unknown is not the same as off.
- Manual, API, and CLI deploy, rollback, and turning Railway auto-deploy back on are not blocked by this file.

A skipped or failed GitHub Deploy run is not proof a host stayed still.

## Railway, as reported, not re-checked here

This change did not call Railway and did not independently verify the readback.

An Ops record at 2026-11-07 15:33:08+01:00 says `serviceInstanceAutoDeployUpdate(false)` on eight app instances, with a later readback of off. It says deployment, replica, and health snapshots were unchanged. It says the native disable removed trigger-backed branch and `checkSuites` fields while the repo stayed connected, and that the previous trigger records were kept outside this repository. This change does not restore or re-enable those triggers and does not edit Railway source config in the repo to put the fields back. The same record says a storefront build already running was not cancelled and may still finish. Firstout's descriptor in that record still showed `@main` while its trigger query was empty; the other six showed branch empty. Do not flatten those two readbacks.

A separate Ops capability note at 2026-11-07 15:35:24+01:00 says Railway `NEEDS_APPROVAL` is skipped for a linked GitHub author with Deployer or higher. That is not mandatory human approval of every release. No named-reviewer policy and no full commit-plus-digest tuple were verified. Reusing a deployment id to redeploy the same service and environment's existing build is described as supported. Accepting an OCI digest and reading that digest back from the running instance were not verified. Connecting an image source is described as building and deploying immediately, so this change does not do that. GitHub user `38779415` is reported to map to Railway user `4a44a268-2832-4329-8923-9eb3a119640d`. An agent session of that account is not a human approval. No artifact gate was activated.

Earlier GitHub reads, not repeated here: ten environments had empty `protection_rules` and `can_admins_bypass` true; organization plan was null; classic branch protection, org rulesets, and Actions permissions returned 403. A 403 means this token could not read or change that endpoint. It is not proof the plan lacks the feature. `main-pr-gate` required reviews were 0. CODEOWNERS would not block the author.

## Not implemented

There is no path that accepts an approval. There is no binding of a person to one target, one commit, and one digest. GitHub environment reviewers are not configured by this change. Railway approval is not turned on. Production is not a place to discover digest behavior.

The full gate stays blocked until three things exist outside this pull request: a deploy credential that agents and pull-request code cannot use, a settings authorization that can require a named human reviewer without an admin bypass, and a non-production test that a digest-pinned deploy does not rebuild and that the running instance reports that digest. Those are not done here.

Merging this pull request is a separate decision. It is not authorized by the author. An independent review of head `a8e51d0a` found the freeze preparation had no new webhook-secret blocker and was not an artifact-approval pipeline. That review is not permission to deploy. A later head of this branch needs its own review.
