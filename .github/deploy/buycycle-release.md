# Buycycle tested-image release path

This is a prepared release path, not approval to use it. It performs no automatic
deployment after a merge. Buycycle's existing Pi runtime and data remain in place
until Leo approves the exact cutover and recovery scope.

## Build, approval and execution

1. The required CI `buycycle image` job runs on native `ubuntu-24.04-arm`, selected
   through Nx affected `container-test`. It builds once and tests the actual image
   with PostgreSQL, synthetic signed Access assertions and the production React
   build. The same harness requires a 702,151-record synthetic import preview
   in a separate no-network container capped at one CPU and 768 MiB with no extra
   swap. All five table counts and hashes must match; missing or failed capacity
   evidence blocks publication. A separate full-size synthetic API fixture uses
   the same image and selected PostgreSQL major: both categories are checked cold
   and warm, then mixed and two-bike concurrent requests drain complete responses
   while health, database readiness and authenticated status are probed. The app
   stays capped at one CPU/768 MiB without extra swap; its disposable PostgreSQL
   fixture uses the explicitly reviewed one-CPU/2 GiB migration budget. This is
   workload regression evidence, not a promise of spare capacity for future data.
   Missing or failed full-API evidence also blocks publication.
   It retains `image.tar` and `evidence.json` outside the public checkout.
   An unaffected job does no image build; an affected job missing its evidence
   fails. The required `ci` aggregate includes this job.
2. Create a tag matching `release/buycycle/pi/YYYYMMDDTHHMMSSZ` at the selected main
   commit. An active repository tag ruleset must prevent update and deletion of
   `refs/tags/release/buycycle/pi/*`, with no bypass actors. Only this fixed tag
   grammar selects Buycycle on the Pi; no app config can select another host.
3. A separate requester App posts the closed JSON below on the configured,
   already reviewed and merged main PR. `issue_comment.created` runs only trusted
   default-branch code. Its read-only validator retrieves the authoritative
   comment, App, bot, repository and PR identities before publication. `prepare`
   retrieves current GitHub facts for the successful **main-push** CI run,
   verifies both required source checks and the exact artifact ID/digest/attempt,
   validates the archive hash, and loads the original image. PR synthetic-merge
   archives and manual CI archives cannot become releases.
4. The workflow tests the loaded image again against the requested PostgreSQL
   major (15 or 17), without rebuilding it, publishes
   it to GHCR, and pulls the resulting immutable registry digest. The registry's
   Linux ARM64 config digest must equal `config_digest`, independently hashed
   from the archive's actual config bytes. Publication is not deployment.
5. The App comment includes the three exact private receipt hashes: controlled
   migration/import, backup/restore, and provider/origin fence. The publication
   freezes its comment ID, exact body hash, request UUID and selected major.
   The protected `production` job shows the selected digest and waits for Leo.
   Its approval artifact binds the exact publication document and comment/nonce.
   The unchanged comment is re-fetched before publication, after protected approval
   and independently by the agent. Human-triggered dispatch publishes only;
   it cannot produce release approval. Reruns, edits, deletion and nonce reuse
   fail closed. Start a new comment with a new UUID when needed.
6. The operator's mutually authenticated client submits only a release run ID and
   UUID to the managed Pi agent. The agent independently retrieves the trusted
   GitHub publication/approval and rechecks tag/checks, automation identity,
   environment protection, Leo's approval and the local receipt hashes/freshness.
   It accepts no requester-supplied image, shell command, file path or credential.
7. The agent reserves durable journals for the run, comment and request UUID,
   pulls the approved digest and
   updates only the fixed `buycycle` Compose `app` service with `--no-build`.
   Success requires actual Docker container/image ID, matching registry/config digests,
   source label, healthy readiness and no host-port bindings. A queued provider
   response or a configured image field is never running-image proof.

## Separate comment requester

The App is separate from the PR publisher and has exactly repository
`Pull requests: write`, `Contents: read`, `Actions: read` and implicit
`Metadata: read`, installed only on `F0rge/f0rge` (repository ID `1194719185`).
It receives no Actions write permission. The prepared operator helper exposes
only identity inspection and posting a strict comment to its configured merged
release PR; it cannot dispatch, edit/delete comments, push, approve, merge,
publish images or deploy. The existing publisher retains its original scope.

The operator helper reuses the explicit macOS Keychain, anonymous-FD RSA JWT,
fixed GitHub HTTPS/no-redirect transport, single-repository token downscoping
and token revocation from the publisher. The keys occupy separate App-slug
accounts in Keychain service `org.f0rge.codex-pr-publisher`. No key/token is
accepted through argv, environment, `gh auth` or the private JSON config.

Use a user-owned mode-0600 config with exactly `app_id`, `slug`,
`installation_id`, `repo_id` and `request_pr_number`. Configure the matching
GitHub repository variables `BUYCYCLE_RELEASE_REQUESTER_APP_SLUG`,
`BUYCYCLE_RELEASE_REQUESTER_APP_ID`, `BUYCYCLE_RELEASE_REQUESTER_BOT_ID` and
`BUYCYCLE_RELEASE_REQUEST_PR_NUMBER` from observed App/bot facts. The managed
Pi policy independently pins these identities and the selected PostgreSQL major.
The fixed PR must already be merged into main. Changing this channel requires a
reviewed configuration update; comments elsewhere cannot request release.

The entire comment is JSON with exactly these fields (placeholders below must
be replaced with real validated values; no Markdown wrapper or extra fields):

```json
{
  "version": 1,
  "source_commit": "<40 lowercase hex>",
  "ci_run_id": 123456,
  "release_tag": "release/buycycle/pi/20261115T090000Z",
  "postgres_major": 15,
  "request_id": "<new canonical UUID>",
  "receipt_hashes": {
    "migration": "<64 lowercase hex>",
    "restore": "<64 lowercase hex>",
    "provider": "<64 lowercase hex>"
  }
}
```

```sh
uv run .github/scripts/f0rge_buycycle_requester.py inspect --config /private/requester.json
uv run .github/scripts/f0rge_buycycle_requester.py post-request \
  --config /private/requester.json --request-file /private/release-request.json
```

The helper checks the fixed merged PR and successful main CI before its single
comment write. An ambiguous response is not retried or auto-edited: inspect the
actual comment/run first. The workflow requires authoritative REST
`performed_via_github_app` matching the registered App even when the event payload
omits it. Missing API evidence blocks activation. Duplicate JSON keys, extra
fields, booleans used as IDs, malformed values and duplicate request UUIDs on
the fixed PR are rejected. Comment inventories are bounded at 1,000 entries;
exceeding that bound fails closed rather than omitting old nonces.

For a PG15 target, the approved comment, publication's exact-image retest,
managed policy and observed provider receipt must all say 15. A source CI image
tested initially with PG17 may be loaded and tested against PG15 without a
rebuild; its canonical config digest must remain identical. PG17-only evidence
cannot authorize that PG15 target. Trusted main code executes the helper and
harness; neither a PR checkout nor code from a selected older source is run.

## Agent seam

The callable implementation is `agent_apply(run_id, request_id, policy)` in
`buycycle_release.py`. The managed server exposes only:

```text
POST /v1/releases
{"release_run_id":123456,"request_id":"canonical-UUID"}
```

Its wrapper must require a client certificate from the dedicated release CA,
use a fixed root-managed policy, limit body size/time/concurrency, and expose no
general command or secret-reading endpoint. Installation and certificate custody
must be independently verified before activation. The helper verifies root-owned,
non-symlink, non-writable-by-others policy/receipt paths. The client private key
must have owner-only permissions. No deployment credential is put in GitHub.

Required policy fields (all paths are fixed on the Pi):

```json
{
  "app":"xi0qwpbyl2d8gf8u3xl13jkv",
  "project_name":"buycycle",
  "compose_path":"/opt/f0rge/apps/buycycle/ops/compose.yml",
  "compose_sha256":"<reviewed-compose-hash>",
  "managed_env_sha256":"<reviewed-runtime-config-hash>",
  "expected_docker_engine_id":"<verified-Pi-Docker-engine-ID>",
  "managed_env_file":"/etc/buycycle/runtime.env",
  "journal_dir":"/var/lib/buycycle-release/journal",
  "active_release_receipt":"/var/lib/buycycle-release/journal/active.json",
  "requester_app_slug":"<verified-dedicated-app-slug>",
  "requester_app_id":123456,
  "requester_bot_id":123457,
  "request_pr_number":1234,
  "postgres_major":15,
  "max_age_seconds":3600,
  "migration_receipt":"/var/lib/buycycle-release/receipts/migration.json",
  "restore_receipt":"/var/lib/buycycle-release/receipts/restore.json",
  "provider_receipt":"/var/lib/buycycle-release/receipts/provider.json",
  "agent_url":"https://<private-managed-agent>/v1/releases",
  "client_cert":"/etc/buycycle/release-client/cert.pem",
  "client_key":"/etc/buycycle/release-client/key.pem",
  "agent_ca":"/etc/buycycle/release-client/agent-ca.pem"
}
```

Each local receipt has `passed:true`, the exact `commit`,
`target:{"host":"pi","app":"xi0qwpbyl2d8gf8u3xl13jkv"}` and timezone-aware
`created_at`. Provider receipt additionally requires true values for
`legacy_collector_fenced`, `source_builds_disabled`, `origin_unpublished`,
`access_policy_verified`, `database_grants_verified` and
`managed_secrets_verified`. Those values must come from the actual controlled
preflight, not edited assertions. Their complete file-byte SHA256 values are
inputs reviewed in the protected release request. The default one-hour receipt
window and seven-day image-test window are conservative initial release limits;
they do not declare an accepted app recovery/freshness target.

The provider receipt also binds `docker_engine_id`, `compose_sha256` and
`managed_env_sha256` to those policy values. All privileged Docker commands force
`unix:///run/docker.sock`, ignore inherited contexts/remote hosts and verify the
actual local engine ID before pulling or starting anything. Changing the runtime
configuration or targeting another daemon invalidates the preflight.
The Docker/Compose subprocess receives only `PATH`, managed `DOCKER_CONFIG`, a
fixed locale and the approved `BUYCYCLE_IMAGE`; its Docker socket is forced.
Ambient Access settings, secret paths, network names and `COMPOSE_*` variables
cannot override the hashed `--env-file`. Preflight uses the same environment
constructor as promotion.
The runtime environment file must be mode `0600`; root ownership alone does not
protect readable database or tunnel credentials.

`image_id` is the local Docker engine's image identifier, which may identify an
OCI index on Docker 29 or the config on another engine. It is evidence about
that test host, and is never compared across hosts. `config_digest` identifies
the actual image configuration consistently. The agent verifies the pinned
registry's ARM64 config and compares its running container to its own freshly
pulled image ID, recording both values in its receipt.

Example commands use Python 3.11 or newer:

```sh
python3 .github/deploy/buycycle_release.py plan --release-run-id RUN --policy /etc/buycycle-release/policy.json
python3 .github/deploy/buycycle_release.py promote --release-run-id RUN --policy /etc/buycycle-release/policy.json
```

`plan` is read-only. `promote` contacts the fixed mTLS agent; that is an actual
deployment and needs the verified approval. `agent-apply` is the same execution
seam for the managed server, not a routine agent SSH path.

## Replay, ambiguity and recovery

A process lock serializes all Buycycle releases, including different run IDs.
Before the first Docker effect, an exclusive `<run-id>-1.json` journal is flushed
alongside `comment-<id>.json` and `request-<UUID>.json`, with file and directory
fsync. Replaying any one of those identities is rejected even after restart or
through a different run ID. A partial reservation stays consumed on failure.
Failed or lost deployment responses record `submission_outcome_unknown`; inspect
the journal and actual container before issuing a new approval. Never delete a
journal to retry a deployment blindly. Release workflow reruns are rejected so
an old environment approval cannot silently authorize another attempt.

After healthy-image verification and the durable journal update, the agent
atomically publishes `active.json` in that same protected journal directory.
The receipt includes the image/config/engine identities and approved Compose
and runtime configuration hashes. The managed collector checks it against the
actual running API before using that image. An update in progress, failed
verification or missing/mismatched receipt holds collection closed.

The migration and backup receipts are prerequisites; the helper does not run
migrations at API startup or discard data. The legacy collector and source-based
automatic deployment must already be fenced. Keep the authoritative PostgreSQL
state after the first new write. Recovery changes code/UI over that state or
restores a verified current backup; restarting stale Turso is not zero-loss
recovery. Cloudflared/private routing and the shared Pi database must be prepared
under their own reviewed configuration before the app service is promoted.

## Remaining activation checks

These source checks and loopback tests do not prove live provider configuration.
Before enabling the requester App, contain historical workflow reruns and all
alternate production credential paths described in the [release hold](README.md).
The App must have exactly PR write plus Actions/Contents/Metadata read. Verify
the real App identity, protection API payload, tag ruleset, independently approved
nonproduction run, managed mTLS agent/certificate custody, private origin, source
build/collector fence, migration/import reconciliation and restore receipts.
Missing or unverifiable facts keep the release closed. Existing services and the
other apps' release holds are not changed by this preparation.

Primary references: [GitHub ARM runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[default-branch issue-comment events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#issue_comment),
[issue-comment API permissions](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment),
[environment required reviewers without deployments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments#using-environments-without-deployments),
[Coolify immutable Docker images](https://coolify.io/docs/applications/deployments/docker-image).
