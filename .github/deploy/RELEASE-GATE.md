# Release gate

This file describes what the repository can enforce today and what it cannot.

## Prepared in this change

`release_gate.py` always returns `deny`. A merge, tag, green CI run, manual dispatch, rerun, pull-request sentence, or boolean in the repository is not an approval. Tests in `test_release_gate.py` cover mismatched SHA, digest, and target; pending, failed, and missing CI; untrusted events and workflow paths; mutable tags; rebuilds; artifact changes after CI; and self-approval.

`.github/workflows/release-gate.yml` is `workflow_dispatch` only. It has `contents: read`, no secrets, and exits 1. It does not call Railway or Coolify.

`.github/workflows/deploy.yml` no longer calls `deploy-reusable.yml` and no longer passes deploy secrets. When this file is the one GitHub runs, the previous automatic webhook and smoke path does not run.

## Not enforced on the current live `main` until this change is merged

Until this pull request is on `main`, GitHub still runs the previous `deploy.yml` from `main`. That file still starts after a successful CI push to `main` and can call Coolify webhooks and Railway smoke. Merging is a separate decision. This pull request must not be merged from the agent that wrote it.

## Still outside this repository even after merge

These routes are not switched off by this change. Their live settings were not readable:

- Railway git autodeploy for services that track `main`, including any storefront or Vellano service connected outside `.github/deploy/manifest.yml`.
- Coolify auto-deploy on git push, as distinct from the GitHub webhook this workflow used to call.
- A person copying Airflow compose or other files onto the Pi.
- `workflow_dispatch` of the previous deploy file on `main` before this change is merged.

A skipped or failed GitHub Deploy workflow is not proof those hosts stayed still.

## Activation that this change does not pretend to do

1. A reviewer other than the author accepts this fail-closed change. Required reviews are currently 0, and the ruleset payload does not show a bypass-actor list. CODEOWNERS alone would not block the author.
2. Confirm GitHub can require a specific person on an environment. The environments read earlier had empty `protection_rules`. The plan feature that adds reviewers was not visible (organization plan was null; some settings APIs returned 403). Do not treat an environment name as that reviewer.
3. Only a later reviewed change may accept an approval that GitHub itself records for one commit and one digest. This repository must still not mint that approval.
4. Separately, with explicit approval, turn off host autodeploy that ignores this workflow. That is not done here.
