# Buycycle GitHub App release requester

This is a registration and activation plan for the prepared
[comment-based release path](buycycle-release.md). Source checks do not prove
that the separate App is registered, installed or verified. Other apps retain
their own release controls; this document grants no release permission.

## Registration and custody

Register a private, F0rge-owned **F0rge Buycycle Release Requester**, with homepage
`https://github.com/F0rge/f0rge`. Verify its resulting slug and IDs rather than
assuming the requested name was available. The
[example manifest](release-requester-app.example.json) is unsubmitted inventory.
Its inactive placeholder webhook is never an operational endpoint.

Use exactly repository **Pull requests: write**, **Contents: read** and
**Actions: read**, plus GitHub's implicit **Metadata: read**. Install only on
`F0rge/f0rge`, repository ID `1194719185`. Leave webhook delivery, event
subscriptions, user OAuth authorization, device flow and organization/account
permissions off. No Actions write permission is required: this App posts a
comment; trusted default-branch automation validates it.

Keep the requester separate from the PR publisher. Store its signing key in the
explicit macOS Keychain backend through the shared pinned helper, using its own
App-slug account. Keep keys and tokens out of source, argv, environment and logs.
The private mode-0600 config contains only observed App/installation/repository
IDs, slug and the fixed, already merged release PR number. The helper verifies
the exact installation and scopes, mints a short-lived single-repository token
and revokes it after use. Its only write is a strict request comment on that PR.
GitHub's PR-write permission is broader than the helper, so key custody remains
a security boundary.

## Safe identity rehearsal

After independent review and the workflow reaching `main`:

1. Verify the installed App's actual permissions and single-repository selection.
   Configure its observed bot/App IDs and fixed merged PR in the workflow and
   protected Pi policy. Test the workflow and managed read identities can read
   the required App/comment metadata; missing or denied evidence blocks release.
2. Prepare one strict request with a real successful main CI run, selected
   PostgreSQL major, new UUID, synthetic receipt hashes, and a well-formed release
   tag that has been confirmed absent. Do not create that tag.
3. Post through the narrow requester helper. Check the real event actor and
   authoritative REST `performed_via_github_app`, comment ID and body hash.
   The trusted validator must accept the identity, then publication must stop
   at the absent tag before Docker, GHCR, protected approval or any Pi call.
   Retain the comment/run URLs and redacted result. Do not retry an ambiguous
   comment write automatically.
4. Record this as identity/event evidence only. It does not prove Leo's protected
   environment approval or authorize deployment. Rejection of changed, deleted,
   duplicate and rerun requests also needs its implemented checks and evidence.

## Activation requirements

The complete path binds the exact request, successful main CI archive, immutable
tag, tested ARM64 image, PostgreSQL compatibility target and three private receipt
hashes through Leo's protected approval and independent managed-agent checks.
Manual workflow dispatch publishes only. The managed agent durably reserves the
run, comment and nonce before Docker effects; it accepts no caller-selected
image, command or path. See [the full protocol](buycycle-release.md).

Contain legacy automatic deploys, manual webhooks, scheduled writers, historical
credentials and other alternate release paths independently. Existing Actions
write credentials can rerun historical workflows; removing that permission from
this new App does not revoke other identities. Verify current data preservation,
encrypted off-device recovery, provider configuration, secret custody, origin
isolation and the actual running image before declaring cutover complete.
Leo must personally approve the protected release; agents never approve through
his account. A comment, passing test or merged PR is not release approval.

References: [App manifest fields](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest),
[issue-comment workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#issue_comment),
[installation token scope and expiry](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app),
and [private-key security](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app).
