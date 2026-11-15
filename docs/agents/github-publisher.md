# GitHub PR publisher

Use the configured `f0rge-codex-publisher` GitHub App to open agent-prepared PRs
to `F0rge/f0rge` `main`. Branch pushes keep the authorized user's Git identity.
The bot authors the PR; Leo performs the required human review in his own GitHub
session. Review/automatic squash merging follows [P-005](../adr/governance.md#p-005);
release authorization follows [P-006](../adr/governance.md#p-006). Independent
agent review and CI remain separate evidence.

If the App, private configuration or Keychain item is unavailable, finish the
branch, checks and PR body and report the precise missing setup. Use a personal
connector, PAT or `gh` account to open the PR only if Leo explicitly requests
that fallback. Existing authorization to open a PR does not choose that fallback.

## Identity and scope

The App requests only repository **Contents: read**, **Pull requests: write** and
GitHub's **Metadata: read**. Install it on the selected `F0rge/f0rge` repository
only, verified by repository ID `1194719185`. It has no Actions, administration,
deployment, secrets or content-write permission. This publisher is separate from
the proposed [release requester](../../.github/deploy/release-requester-app.md).

GitHub's PR-write permission covers more operations than this helper exposes.
The reviewed [publisher helper](../../.github/scripts/f0rge_pr_publisher.py) offers
only `inspect` and `open-pr`; it has no review, approval, merge, push, settings or
deployment operation. Protect the App signing key accordingly. A helper's narrow
interface is not a sandbox against other code running as the same local user.

The private key belongs in the explicit macOS Keychain backend through pinned
`keyring==25.6.0`, service `org.f0rge.codex-pr-publisher`, account equal to the
verified App slug. Registration passes the PEM directly to `store_key` in memory.
Keep keys and short-lived JWTs/installation tokens out of command arguments,
terminal output, repository files, environment variables and PR content. Each
invocation mints a repository/permission-scoped token, checks its expiry and
revokes it on completion. A revocation error requires inspection; it is not proof
that a preceding PR write did not happen.
See GitHub's [installation-token scope and expiry reference](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).

## Setup and activation evidence

Registration, installation and key custody need their own task authorization.
This guide is a procedure, not proof that an App has been installed or verified.
Keep GitHub branch/review/CODEOWNERS protections in force during setup.

Store the observed public identifiers outside the repository at
`~/.config/f0rge/github-publisher.json`: user-owned mode `0600`, inside a private
mode-`0700` directory with protected ancestors. The helper accepts only these
fields and requires an explicit absolute `--config` path:

```json
{
  "app_id": 0,
  "slug": "f0rge-codex-publisher",
  "installation_id": 0,
  "repo_id": 1194719185
}
```

The zero IDs are placeholders and deliberately fail validation. Replace them
with actual registration/installation IDs. This metadata contains no signing key
or token. Do not change global GitHub login, user-global agent instructions or
repository Git configuration to select the publisher.

After authorized setup, use the reviewed helper from a trusted checkout:

```sh
uv run --script .github/scripts/f0rge_pr_publisher.py inspect \
  --config "$HOME/.config/f0rge/github-publisher.json"
```

Inspection authenticates the App, verifies App/installation/bot IDs and exact
permissions, checks the active selected-repository installation and confirms the
token's single-repository access and the repository identity/default branch. It mints and revokes its own short-lived
token; it creates no PR and changes no GitHub settings. Retain only its non-secret
facts and the time of verification as activation evidence. Every `open-pr`
invocation performs the same checks again.

Verify the review boundary with an authorized Markdown-only test PR: confirm the
bot author and expected head SHA, observe the required human/code-owner review,
then ask Leo to perform that review himself. Record the actual PR, author/bot ID,
reviewer, reviewed commit and required-check results. An agent must not click
Approve or call a review API through Leo's signed-in browser or credentials.
Neither a test approval nor App installation approves another PR or a release.

### Verified checkpoint: 15 November 2026

The App was installed and real `inspect` checks passed. The App created
[Markdown smoke PR #945](https://github.com/F0rge/f0rge/pull/945) at
`25d2fe829c03915819255c35349534447d06ac07`; its checks passed and
[Leo personally approved it](https://github.com/F0rge/f0rge/pull/945#pullrequestreview-5910358412).
That verifies bot authorship and the human-review boundary, not merge activation.

GitHub's `allow_auto_merge` setting is enabled, with squash title/body defaults
`PR_TITLE`/`PR_BODY`. Main review ruleset `27305147` was strengthened from zero
to **one required general approval**, retaining code-owner review, stale-review
dismissal, resolved threads and no bypass. The global
Leo-only CODEOWNERS change is prepared for review and has **not reached main**;
the old file can still request Luis. Default automatic merging remains pending
that reviewed ownership change and verification of the effective rules below.
No current PR was armed, merged or deployed by this setup task.

## Publish a prepared branch

Complete the [PR process](pr-process.md), relevant checks and independent review
first. Push the authorized `codex/*` branch through the normal Git identity.
Write the exact five-section PR body to a private file with actual newlines;
keep the complete ADR table, evidence and visible gaps.

From the repository root:

```sh
publisher_head="$(git branch --show-current)"
publisher_sha="$(git rev-parse HEAD)"
publisher_result="$(uv run --script .github/scripts/f0rge_pr_publisher.py open-pr \
  --config "$HOME/.config/f0rge/github-publisher.json" \
  --head "$publisher_head" --expected-head "$publisher_sha" \
  --title 'feat(scope): explain the change' \
  --body-file /absolute/private/pr-body.md)"
```

The helper verifies the remote branch immediately before creation and checks the
returned PR's repository, `main` base, branch, exact head SHA and bot author. It
returns a matching existing bot PR instead of duplicating it. GitHub has no atomic
expected-head condition in its [create-PR API](https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request): a concurrent branch push can still
race the request. An error may therefore mean a PR exists. Inspect GitHub's
current state before retrying; do not automatically close or recreate uncertain
writes. Confirm the returned PR in GitHub and retain its URL for human review.

## Default native squash auto-merge

After activation, bot-authored PRs use GitHub's native auto-merge queue through
the existing authorized `gh` user identity. The publisher App still only inspects
or opens PRs. No new merge App, custom merge workflow, token capture or global
login change is needed. Queuing merge is not submitting Leo's human review.

Before using the default, verify the actual `main` CODEOWNERS file names Leo as
the sole required owner for all files and the effective rules require code-owner
review, at least one general approval, stale-review dismissal, successful CI and
resolved review threads, with no bypass. Verify squash/auto-merge settings.
Confirm `gh api user` identifies Leo's existing personal User
(`leothesouthafrican`, ID `38779415`); an inherited `GH_TOKEN`/`GITHUB_TOKEN` must
not silently select an Actions or other actor and suppress the subsequent push
workflows. This checks identity without reading tokens or changing login.
An unverified or not-yet-activated
policy leaves the PR unarmed; a task explicitly withholding merging also leaves
its PR unarmed, even if already approved and green.

For a task that permits merging under P-005, use the verified publisher result
and expected source SHA:

```sh
set -euo pipefail
gh api --hostname github.com user \
  --jq 'select(.login == "leothesouthafrican" and .id == 38779415 and .type == "User") | .login' \
  | python3 -c 'import sys; assert sys.stdin.read().strip() == "leothesouthafrican", "Queueing identity must be Leo"'
publisher_pr_url="$(printf '%s' "$publisher_result" | python3 -c 'import json,sys; print(json.load(sys.stdin)["url"])')"
gh pr merge "$publisher_pr_url" --repo F0rge/f0rge --squash --auto --match-head-commit "$publisher_sha"
```

This can merge immediately when all requirements already pass. It never supplies
an approval or bypasses a GitHub requirement; do not use `--admin`, weaken rules
or submit a review through Leo's credentials. Observe the actual queued/merged
state and record it rather than treating command success as a merge receipt.

`--match-head-commit` checks the head when queuing. It does not pin the eventual
merge SHA. GitHub dismisses approvals when reviewable code changes, while
unchanged-diff rebases or empty commits may retain approval. New checks and other
GitHub requirements still apply. Do not claim a fresh review for every SHA change.
Firstout CD independently requires its exact-head review/provenance evidence;
obtain Leo's fresh head approval if native GitHub retained an older commit's
review, or CD can remain paused. Other apps, including
Buycycle, still need separate production-release approval under P-006.

## Replace a PR with unchanged code

GitHub cannot change an existing PR's author. When Leo authorizes replacement:

1. Record the original PR's base, exact head SHA and ordered commit list.
2. Create and push an authorized `codex/*` alias branch at that **same SHA**.
   Preserve every commit; do not add a commit or rebase just to change authorship.
3. Open the alias through the App with that expected SHA and the complete updated
   description, linking the original PR.
4. Verify bot authorship, `main` base, identical source SHA/commits and the required
   checks on the replacement. Request Leo's actual human review where required.
   Old reviews and test-PR approval are not transferred approval.
5. Close the original only after the replacement is verified and closing was
   explicitly authorized. The open-only helper does not perform this operation.

A same-SHA replacement preserves source artifact identity; it does not make an
old PR's checks, reviews or synthetic merge artifact a production release grant.
Follow P-005 for default native squash merging after activation and P-006 for
any subsequent release. A task's explicit no-merge instruction keeps its PR
unarmed.

## Revoke or repair access

Use an authorized administrator action to suspend/uninstall the selected App
installation or revoke its signing key in GitHub. Remove the matching Keychain
item and private metadata when appropriate; leave personal GitHub login and
unrelated credentials untouched. Expiring one installation token does not revoke
the long-lived signing key's ability to mint another. Re-run `inspect` after
repair or rotation; resume App publishing only after the exact identity,
permissions and repository selection are verified again.
