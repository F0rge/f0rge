# Marrow frontend

Daily symptom check-in UI built with Next.js, React, strict TypeScript and the
shared `@f0rge/ui` kit. The app uses Plus Jakarta Sans and Marrow's token skin.
This is an existing app; the [ADR index](../../../docs/adr/README.md) defines the
stack for new apps.

## Run locally

Install the npm workspaces once from the repository root:

```bash
npm ci
npx nx run marrow-frontend:dev
```

Open <http://localhost:3000>. Start Marrow's PostgreSQL database and API separately
using the [root instructions](../../../AGENTS.md#running-locally). Requests under
`/api` are proxied to the API at `http://localhost:8000` by default; `API_URL`
overrides that address.

## Checks

Run from the repository root:

```bash
npx nx run-many -t lint typecheck test build --projects marrow-frontend
npx nx run marrow-frontend:codegen:check
npx nx run marrow-frontend:e2e
```

The browser checks need the running API and frontend. API types are generated
from Marrow's backend contract; do not edit generated files by hand. Shared UI
primitives and forms live in `libs/ui`; inspect them with
`npx nx run f0rge-ui:storybook`.

## Build and release

The [Dockerfile](Dockerfile) uses the repository root as its build context and
produces Next.js standalone output. The npm workspace is named `frontend`, while
its Nx project is named `marrow-frontend`; existing Docker and CI commands use
both identifiers.

[railway.toml](railway.toml) describes the frontend service configuration. See the
[deployment guidance](../../../.github/deploy/README.md) for the release workflow.
Production releases require Leo's approval.
