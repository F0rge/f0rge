# Buycycle

Private road/gravel bike and wheelset deal finder. This PR prepares the ADR
migration; the existing Pi service and all its data remain unchanged.

Run the production app locally with synthetic listings and identity:

```sh
python3 apps/buycycle/ops/dev.py
```

Open `http://127.0.0.1:8090`. Docker, Node, Rust and libpq are prerequisites.
Collection is disabled; no live feed, email or production data is used.

The new app uses Rust/Actix/Diesel/PostgreSQL and React/Vite/strict TypeScript,
actual Primer and TanStack Query/Router/Form. The API verifies Cloudflare Access
assertions. Rust contracts generate the frontend client; shared identity, error
and UI mechanisms live under `libs/`.

- [Work plan and acceptance criteria](docs/adr-migration-plan.md)
- [Data preservation and recovery](docs/data-migration.md)
- [Operations and safe checks](ops/README.md)
- [Verification and limits](docs/verification.md)
- [Production readiness and remaining gates](docs/ops-readiness.md)

The legacy `tracker/`, `dashboard/`, root Dockerfile and `deploy/` runbook are
what runs today: the pipeline releases them as Nx project `buycycle`. The new
backend and frontend have no deploy block and are not released. Do not start the
legacy writer beside the new collector. The cutover to the new app requires Leo's
separate approval, current data/browser reconciliation and all provider/recovery gates. Never commit private
databases, exports, user state, secrets or feed keys to this public repository.
