# Releasing

A reviewed merge to `main` with CI passing releases every App the change affects ([P-006](../../docs/adr/governance.md#p-006)). Terms (Project, App, Host, Artifact, Release): [glossary](../CONTEXT.md).

[`ci.yml`](../workflows/ci.yml) builds and health-checks one Artifact per deployable Project and, on `main`, pushes it as `ghcr.io/f0rge/<nx project>:<commit sha>`. Its last job calls [`cd.yml`](../workflows/cd.yml), which runs one job per affected App in the GitHub environment named after the App. That job runs `deploy.mjs`.

## The two programs

- **`deployables.mjs`** lists what can be released. It finds every `project.json` with a deploy block and groups the Projects by their `scope:<app>` tag. `node .github/deploy/deployables.mjs` prints the list. It fails when an App mixes Hosts or a deployable Project has no scope tag.
- **`deploy.mjs --app <app> --commit <sha>`** releases every service of the App at that commit, services with a `preDeployCommand` first, and waits for each to become healthy.
  - Railway: sets the service's image, health path, pre-deploy and start command, and triggers a deployment. Railway's own health check decides success. Needs `RAILWAY_TOKEN`, a project token.
  - Pi: sets the image tag on the Coolify "Docker image" application with the service's name and triggers a deployment. Needs `COOLIFY_URL` and `COOLIFY_TOKEN`. `preDeployCommand` and `startCommand` are refused on a Pi service. Coolify's own Healthcheck stays off: each Pi image carries a Docker `HEALTHCHECK`, and a service counts as healthy only when Coolify reports `running:healthy` (or `running:unknown`) for the whole settle window.
  - Before changing a service it records the image the Host has it configured to run. On failure it puts each service it touched back on that image, in reverse order and without its `preDeployCommand`, then exits non-zero. A service that had no previous image (a first Release, or a service still built from the repository) is left as it is.
  - It fails closed, before changing anything, when a token is missing or a service is not found by name on the Host.

| Variable | Default | Meaning |
|---|---|---|
| `DEPLOY_TIMEOUT_SECONDS` | `900` | How long one service may take to become healthy. |
| `DEPLOY_SETTLE_SECONDS` | `90` | Pi only: how long a container must stay up and not unhealthy before it counts as healthy. |

Both are plain Node with no dependencies. Tests: `npx nx run f0rge-deploy:test`.

## Deploy block

A Project is deployable when its `project.json` has this block. Its App is its `scope:<app>` tag. All deployable Projects of one App share one `host`.

```json
"metadata": {
  "deploy": {
    "host": "railway",
    "services": [
      { "name": "example-api", "healthcheckPath": "/health", "preDeployCommand": "…", "startCommand": "…" },
      { "name": "example-worker", "startCommand": "…" }
    ]
  }
}
```

`host` is `railway` or `pi`. Only `name` is required per service; it is the service's name on Railway or the application's name in Coolify. One Project can back several services, all running the same Artifact.

The block also carries what CI needs to build and check the Artifact: `check.port` (required), and optionally `check.path`, `check.migrate`, `check.postgres`, `check.redis`, `check.env`, `build.context` and `build.args`. [`image.mjs`](../scripts/image.mjs) documents them; `npx nx run <project>:image` runs the same build and check locally. Build arguments are public.

## Release or roll back by hand

```bash
gh workflow run cd.yml -f app=<app> -f commit=<sha>
```

Use it for a first Release, a redeploy or a rollback. `<app>` is `firstout`, `marrow`, `daskasas`, `dk`, `envmon` or `buycycle`. `<sha>` is a full commit that CI built on `main`; the run fails if any of the App's Artifacts is missing at that commit. The App's GitHub environment holds its tokens and shows its deploy history.

Rolling back by hand across a migration runs the older commit's `preDeployCommand` against the newer schema. If that fails, the Release fails and each service is put back on the image it ran before.

## Switching an App at its Host

Each App is switched once, by Leo: the Host is pointed at images, and the token goes into the App's GitHub environment. `switch/<app>.sh` walks through the steps for that App. Until then the App fails closed.

The first `main` run after this pipeline merges tries to release all six Apps. Each App that is not yet switched fails closed, and later runs on `main` retry it until every App is green.

Order: dk tag printer, environment monitor, Buycycle, DasKasas storefront, Marrow, Firstout. Storefront and Marrow must be switched before 1 December 2026, when Railway stops reading config files from the repo.

## Accepted ceilings

- Nothing checks a whole App before production.
- No backup check before migrations.
- A migration that is not backward compatible can make the automatic rollback fail.
- A commit tag can in principle be overwritten; only `main` CI pushes.
- On the Pi a bad Release causes downtime until the rollback completes.
