# Proposed GitHub App release requester

This is a **design and example**, not a registered App or an active release
path. The [example manifest](release-requester-app.example.json) has not been
submitted to GitHub; its name, webhook fields and final registration must be
validated in an isolated sandbox. It does not install an App or authorize a
release. The [release hold](README.md) remains in force.

## Scope and risks

The proposed private App requests only repository **Actions: write** for
dispatch; GitHub also supplies repository metadata access as applicable. It
requests no event subscriptions or user OAuth authorization. It should be
installed on the single intended repository, never all organization
repositories. When minting a token, explicitly select that repository and the
needed permissions. GitHub installation tokens expire after one hour, but the
App's private key can mint more tokens and must be protected for its full life.

**Actions: write can enable disabled workflows and rerun historical workflows.**
Limiting the token to a repository does not restrict it to the new workflow or
prevent a rerun from using an old workflow definition. Before any
production-repository installation or key distribution, identify and contain historical deployment
credentials, workflow reruns, direct provider access, automatic provider
triggers and other alternate release paths. Verify the controls independently.
An App identity alone does not provide that containment.

Use a managed, access-controlled signing key or vault; do not commit the key,
print tokens, expose them to pull-request code, or place them in a broadly
accessible repository secret. Define key ownership, rotation and revocation,
and restrict who and what can request signatures. The requester must not grant
itself approval or access to deployment credentials. An agent acting as Leo is
not an independent requester.

## Sandbox setup and validation

These steps are for a separate disposable, nonproduction repository with no
production credentials, providers or connections. Use a public sandbox or a
private sandbox on a GitHub plan that supports required reviewers and the
relevant protection rules; verify those rules are effective. Registration,
installation and secret changes are separate operations; this document performs
none.

1. Arrange secure capture and custody of the private key returned by the
   manifest registration flow before registering. Create a private test App
   from the example, replacing the candidate name if needed. Check GitHub
   accepts the inactive webhook settings and that no event or user authorization
   is requested. Never use the placeholder webhook
   as a real endpoint. Install the test App only on the sandbox repository.
2. Put a no-effect `workflow_dispatch` workflow on the sandbox default branch.
   Its protected test environment must require Leo as reviewer, prevent
   self-review and disable administrator bypass. Its jobs must have no
   deployment credentials, provider calls or production target. Record the
   effective settings; the `production` environment in the real repository is
   not part of this test.
3. Dispatch with a short-lived installation token and check the run's actual
   `github.actor` and `github.actor_id`. Confirm the no-effect job waits for
   Leo, and that Leo's explicit review permits it to finish. Separately confirm
   that a run initiated as Leo cannot be approved by Leo. Never infer the actor
   from how the token was obtained.
4. Rerun an approved and a rejected or cancelled sandbox run, including a rerun
   initiated by a different actor. Record `github.actor`,
   `github.triggering_actor`, run ID and attempt, and whether a fresh review is
   required. Treat missing, reused or bypassed approval as a failure; do not
   assume GitHub reruns provide fresh approval. Confirm a historical no-effect
   sandbox workflow can be rerun with the App token to demonstrate the scope of
   Actions: write.
5. Verify a token narrowed to the sandbox repository cannot dispatch in a
   second repository. Check the App's effective installation permissions and
   token expiry without recording token values. Revoke sandbox credentials and
   remove the sandbox installation after the test.

`workflow_dispatch` only triggers when the workflow exists on the default
branch. A PR-only workflow in the real repository is therefore not proof of
the production behavior. Preserve run URLs and redacted results for independent
security, delivery, operations and quality review.

## Before activation

Beyond the identity and alternate-path controls above, the release still needs
a protected tag design selecting the destination (P-045), trusted evidence
linking the exact tested immutable artifact to the commit and target, promotion
without a rebuild, and independent verification of the running artifact and
health (P-046). Establish durable expiry and replay handling and demonstrate
it across retries. GitHub approval must be Leo's explicit approval of each
production release (P-006). Until those conditions and the release hold are
met, do not enable a deployment path or give the App production access.

References: [App manifest fields](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest),
[workflow dispatch permission](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
[rerun permission](https://docs.github.com/en/rest/actions/workflow-runs#re-run-a-workflow),
[installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app),
[private-key security](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app),
[actor and rerun contexts](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#github-context),
and [workflow dispatch behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).
