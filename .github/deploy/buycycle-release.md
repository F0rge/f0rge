# Buycycle tested-image release path

This is a prepared release path, not approval to use it. It performs no automatic
deployment after a merge. Buycycle's existing Pi runtime and data remain in place
until Leo approves the exact cutover and recovery scope.

## Build, approval and execution

1. The required CI `buycycle image` job runs on native `ubuntu-24.04-arm`, selected
   through Nx affected `container-test`. It builds once and tests the actual image
   with PostgreSQL, synthetic signed Access assertions and the production React
   build. It retains `image.tar` and `evidence.json` outside the public checkout.
   An unaffected job does no image build; an affected job missing its evidence
   fails. The required `ci` aggregate includes this job.
2. Create a tag matching `release/buycycle/pi/YYYYMMDDTHHMMSSZ` at the selected main
   commit. An active repository tag ruleset must prevent update and deletion of
   `refs/tags/release/buycycle/pi/*`, with no bypass actors. Only this fixed tag
   grammar selects Buycycle on the Pi; no app config can select another host.
3. Manually run `release-buycycle.yml` on `main` with that commit/tag and its
   successful **main-push** CI run ID. `prepare` retrieves current GitHub facts,
   verifies both required source checks and the exact artifact ID/digest/attempt,
   validates the archive hash, and loads the original image. PR synthetic-merge
   archives and manual CI archives cannot become releases.
4. The workflow tests the loaded image again without rebuilding it, publishes
   it to GHCR, and pulls the resulting immutable registry digest. The registry's
   Linux ARM64 config digest must equal `config_digest`, independently hashed
   from the archive's actual config bytes. Publication is not deployment.
5. To request release approval, a separately configured GitHub App starts a new
   workflow run with `request_approval=true` and the three exact private receipt
   hashes: controlled migration/import, backup/restore, and provider/origin fence.
   The protected `production` job shows the selected digest and waits for Leo.
   Its approval artifact binds the exact publication document. Human-triggered
   or rerun requests cannot authorize a release. Start a new request when needed.
6. The operator's mutually authenticated client submits only a release run ID and
   UUID to the managed Pi agent. The agent independently retrieves the trusted
   GitHub publication/approval and rechecks tag/checks, automation identity,
   environment protection, Leo's approval and the local receipt hashes/freshness.
   It accepts no requester-supplied image, shell command, file path or credential.
7. The agent reserves a durable exclusive journal, pulls the approved digest and
   updates only the fixed `buycycle` Compose `app` service with `--no-build`.
   Success requires actual Docker container/image ID, matching registry/config digests,
   source label, healthy readiness and no host-port bindings. A queued provider
   response or a configured image field is never running-image proof.

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
with file and directory fsync. Replaying that run is rejected even after restart.
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
The App may have only Actions write and optional Contents/Metadata read. Verify
the real App identity, protection API payload, tag ruleset, independently approved
nonproduction run, managed mTLS agent/certificate custody, private origin, source
build/collector fence, migration/import reconciliation and restore receipts.
Missing or unverifiable facts keep the release closed. Existing services and the
other apps' release holds are not changed by this preparation.

Primary references: [GitHub ARM runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[environment required reviewers without deployments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments#using-environments-without-deployments),
[Coolify immutable Docker images](https://coolify.io/docs/applications/deployments/docker-image).
