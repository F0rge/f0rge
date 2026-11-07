# Approval harness

This module plans a release tuple. It does not perform one. `EFFECTS_ENABLED` is `False`. `evaluate()` can return `permit` for a simulated receipt. `execute()` still performs no provider call. A permit does not prove that Leo acted, and it does not prove a running image digest.

## Requester and approver

The approver is GitHub user `38779415`. The requester must be a GitHub App installation, and that id must not be `38779415`. `prevent_self_review` stays true, so the person who starts the run cannot approve it. If the starter is Leo, or an agent using Leo's credentials, Leo cannot approve that run. Do not turn self-review prevention off to avoid that deadlock.

An API field that says the reviewer id is `38779415` is not proof of a person when the reader is an agent holding that user's credentials. The only receipt source this module accepts, and only inside the simulated boundary, is `github_environment_api_read_by_non_approver_app`: a read by an app installation token that is not Leo's user token. This repository does not fetch that read. A boolean, a JSON file, or a signature whose key the agent holds is not an approval.

The app is not created here. If it is created later, the minimum repository installation on `F0rge/f0rge` is Actions read-and-write for `workflow_dispatch`, contents read, and the mandatory metadata read. It does not get Administration, secrets, or environment permissions, so it cannot change reviewers or read the Coolify and smoke names. Its token is stored where an agent that holds Leo's user credentials cannot read it. That store is not created here. Leo remains the owner and can still deploy by hand. That break-glass is outside this module.

## Candidate environments

These ids are from the box read at 2026-11-07 15:57:28+01:00. All ten environments were unprotected. This file does not change them.

| GitHub environment | Id | What may be bound |
|---|---|---|
| Marrow / production | `19158860710` | four Marrow app services on Railway project `a633a271-5bb0-461e-8eb5-1acb9e126a59`, environment `ff59293a-ac24-4e1c-8d19-0756bc577016` |
| Firstout / production | `24561991680` | two Firstout app services on Railway project `c76d8df1-d839-454c-a94a-79b930deaf38`, environment `9f7b0c34-bd95-442b-b746-a9791dcc2895` |
| storefront / production | `23387956905` | `storefront` and `storefront-commerce` on Railway project `d58a2884-d366-4230-9555-8b7bb4e42d4f`, environment `d73ff2d5-816d-4bc8-85b4-71a85b0398fa` |
| DasKasas / production | `24635670941` | not bound |

Railway project `d58a2884` is named DasKasas and is where the storefront services run. GitHub environment `DasKasas / production` is a different object. dk tag-printer, buycycle, and environment-monitor stay unmapped. The generic environment `production` (`17911756005`) is not a target.

A same-service Railway deployment id can be reused only when the receipt says that deployment was built from the approved 40-character SHA. That is the supported reuse primitive. An OCI digest is not accepted: no running-digest receipt has been verified, and connecting an image source is described as building immediately. Live deployment ids from 2026-11-07 are builds of `ca3bc0fb`, not of later commits, and they are not an allow-list.

## What stays off

Workflow `253335437` (Deploy) was reported `disabled_manually`. This module does not enable it. Railway push auto-deploy for the eight app services was reported off. This module does not turn it on. `SMOKE_EMAIL` and `SMOKE_PASSWORD` stay. The six `COOLIFY_*` names stay until a separate reviewed custody step; org secrets shared with this repository were reported as an empty list, and Depot's historical copy of `COOLIFY_BASE_URL`, older `COOLIFY_WEBHOOK_DK_*` names, and the smoke names is still an unknown holder, so values are not replaced.

## Smallest later activation

1. Leo, not an agent session, confirms he can recover the six Coolify values without sending them to an agent. Unknown holders block replacing those values.
2. Create the app above and keep its installation token out of the agent. Do not use Leo's user token as the requester.
3. On only the three bound environments, a reviewed settings write sets reviewer `38779415`, `prevent_self_review` true, `can_admins_bypass` false, and deployment branch policy `main`. Administration write is not yet proved. A 403 stops the attempt. Do not edit the other seven environments.
4. A job on `main` may read the review with the app token and call `evaluate`. `execute` stays disabled until a separate change, after these tests, is reviewed. This pull request does not add that job.
