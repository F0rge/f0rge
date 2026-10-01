# Storefront private Railway preview

Issue #759 asks for a private hosted Storefront with isolated Medusa data
services, a real Firstout SKU round-trip, health checks, a rollback path, and a
monthly total below USD 50.

**Status:** an existing Storefront web service is running in the Vellano
`develop` environment, but the isolated preview required by #759 is not
provisioned or verified. No hosted SKU round-trip or cost telemetry is
available. Keep #759 open until the isolated topology, hosted checks, and
measured monthly cost are recorded. A dedicated Firstout machine credential
and Clerk/Peach development credentials still require an owner.

### Read-only hosted audit (2026-09-30 UTC)

Railway metadata was checked with explicit project and environment IDs; no
variables or logs were read, and no infrastructure was changed. The project is
**Vellano** (`c76d8df1-d839-454c-a94a-79b930deaf38`), the existing Firstout /
Vellano project. Its `production` environment has ID
`a639e365-f653-44db-a46d-a6a94e083894` and zero service instances. Its
`develop` environment (`7a8ce6f1-c514-4e5d-9c50-4b7918865321`) has one
successful Storefront web deployment, commit
`33c01651ecfb5f09003157dd35784a5cb91430d8` on `develop`, at
`https://storefront-develop-6009.up.railway.app`. The project service list
contains `storefront`, `vellano-frontend`, `vellano-api`, and `Postgres`; it
does not show dedicated Storefront Medusa or Redis services. This does not
demonstrate the project and data-service isolation required above.

Unauthenticated `GET /api/health` returned `200` with exactly
`{"status":"ok"}`. Unauthenticated `GET /` returned `503`, without a
`WWW-Authenticate` challenge, and included
`X-Robots-Tag: noindex, nofollow, noarchive`. The liveness result is healthy;
the protected web journey is not verified. The deployment's preview credential
configuration was not inspected, so the cause of the `503` is undetermined.
No SKU parity, customer page, dedicated Firstout credential, monitoring/cost
alert, or Railway usage measurement was verified. Keep this existing service
separate from any new isolated preview work and do not connect it to Firstout
or replace its data services as part of this runbook.

## Isolation and access rules

- Create a new Railway project named **F0rge Storefront Preview**, with one
  environment named **private-preview**. Do not reuse the Firstout/Vellano or
  Marrow projects, their services, their databases, Redis instances, buckets,
  or credentials.
- Start with one web service, one shared-mode Medusa service, one dedicated
  Postgres service, and one dedicated Redis service. Do not create a separate
  staging stack for this preview.
- Generate an HTTPS Railway hostname for the **web** service only. Do not add
  custom DNS or generate a public domain for Medusa, Postgres, or Redis. The
  web server connects to Medusa over Railway's private network.
- The Next.js proxy requires HTTP Basic Auth for every non-development request.
  Set STOREFRONT_PREVIEW_USERNAME and STOREFRONT_PREVIEW_PASSWORD as
  server-only web-service variables. The password must be at least 32
  characters and the username must not contain `:`. Missing or weak credentials return 503; unauthenticated
  requests return 401. Never prefix these variables with NEXT_PUBLIC_ or
  pass them as Docker build arguments.
- GET /api/health is the sole unauthenticated exception. It returns only
  { "status": "ok" }; it reports no database, Redis, or credential details.
  Page metadata and X-Robots-Tag keep the preview out of search indexes. Keep
  STOREFRONT_INDEXING_ENABLED=false.
- Keep hosted test payment disabled and use the hosted runtime kind. Do not
  configure Peach, real payment providers, Clerk accounts, or public sales for
  this preview. The local test payment provider is rejected in production and
  hosted runtimes.
- Do not change workspace-wide Railway billing caps. If the available plan
  offers only workspace-wide controls, leave them untouched and get owner
  approval before a plan purchase or material budget change.

## Railway service configuration

For both app services, keep Railway's Root Directory at the repository root.
The Docker build context must remain the repository root.

| Service | Build configuration | Domain | Health check |
| --- | --- | --- | --- |
| storefront-web | `RAILWAY_DOCKERFILE_PATH=apps/storefront/web/Dockerfile` | Railway HTTPS hostname; Basic Auth protected | /api/health |
| storefront-commerce | `RAILWAY_DOCKERFILE_PATH=apps/storefront/commerce/Dockerfile` | Private network only | /health |
| storefront-postgres | Railway PostgreSQL plugin | Private network only | Railway-managed |
| storefront-redis | Railway Redis plugin | Private network only | Railway-managed |

Create new app services with the Dockerfile path above and set Medusa's
pre-deploy command to `node /app/node_modules/.bin/medusa db:migrate`. Its
runtime working directory is the compiled `.medusa/server` folder. Do not
select the checked-in `railway.toml` files for new services: Railway's new
service flow no longer uses legacy Config as Code files ([Railway documentation](https://docs.railway.com/config-as-code)). Use Railway service
references for the private database and Redis URLs; never paste connection
strings into source, CI logs, or this runbook. Hosted Medusa fails closed unless
its dedicated database and Redis URLs exist and its JWT, cookie, and BFF
secrets each contain at least 32 characters. Configure the remaining
service-native Medusa settings from
[the commerce environment example](../commerce/.env.example), using the
dedicated Storefront services and the generated web origin.

Set values in Railway's protected variable editor or an approved secret
manager. This table lists only the Storefront integration variables and their
intent; it contains no credential values.

| Service | Variable names | Notes |
| --- | --- | --- |
| Web | MEDUSA_BACKEND_URL, NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY, NEXT_PUBLIC_BASE_URL, STOREFRONT_BFF_SECRET, STOREFRONT_PREVIEW_USERNAME, STOREFRONT_PREVIEW_PASSWORD, STOREFRONT_INDEXING_ENABLED, STOREFRONT_RUNTIME_KIND | Medusa URL must be its private service address. The BFF secret must match commerce and be at least 32 characters. Basic Auth username must not contain `:`; password must be at least 32 characters. Only the publishable key and base URL use NEXT_PUBLIC_. Set runtime kind to hosted and keep indexing false. |
| Commerce | DATABASE_URL, REDIS_URL, JWT_SECRET, COOKIE_SECRET, FIRSTOUT_OPS_URL, FIRSTOUT_OPS_TOKEN, FIRSTOUT_OPS_COMPANY_ID, STOREFRONT_BFF_SECRET, STOREFRONT_TEST_PAYMENT_ENABLED, STOREFRONT_RUNTIME_KIND, STOREFRONT_VAT_RATE_PERCENT, STOREFRONT_GAUTENG_DELIVERY_ZONES | Use dedicated private PG/Redis references. JWT, cookie, and BFF secrets must each be at least 32 characters. Keep the machine token only on commerce. Firstout credentials are optional for read-only boot but required for SKU sync and acceptance. Keep test payment disabled and delivery rates unset until Operations approves them. |

Firstout checks a static machine credential and the exact hostname of its own
API request. The allowed hostname belongs to the Firstout API ingress, not the
Storefront web host. There is no token-issuance endpoint in the repository. An
owner must provision a distinct Storefront machine token through the approved
Firstout environment path. Do not reuse another integration's token or change
the Firstout hostname allowlist for this preview.

## Provisioning and smoke sequence

After the dedicated Ops credential is available, an owner can create the
project and services in this order:

1. Create the new project and private-preview environment. Add its own Postgres
   and Redis services, then create the commerce and web services from this
   repository. Confirm the project and service names before the first deploy.
2. Select each app service's config file above. Do not set a subdirectory Root
   Directory. Configure private data-service references and Medusa's
   server-only variables. Keep FIRSTOUT_OPS_TOKEN only on commerce.
3. Generate the web service's Railway HTTPS hostname. Set that exact origin in
   NEXT_PUBLIC_BASE_URL and the required Medusa CORS settings. Set strong
   Basic Auth credentials on the web service. Do not configure custom DNS.
4. Deploy Medusa and confirm its /health check succeeds. Run the documented
   first-time bootstrap and source sync from the Medusa service context:

   ~~~bash
   cd /app/apps/storefront/commerce/.medusa/server
   node /app/node_modules/.bin/medusa exec ./src/scripts/bootstrap-storefront.js
   node /app/node_modules/.bin/medusa exec ./src/scripts/sync-firstout.js
   ~~~

   The migration runs before deploy. Obtain the Medusa publishable key from its
   Admin, set it on the web service, then build/deploy the web service.
5. Without credentials, request / and /product/<sku> and confirm 401 plus a
   Basic Auth challenge. Request /api/health and confirm 200 with only the
   documented status body. All responses must carry
   X-Robots-Tag: noindex, nofollow, noarchive.
6. In a private browser session, authenticate and visit
   /product/<source-sku-uuid>. Confirm its title, ZAR price, and stock match
   Firstout. Do not add the SKU to a bag, start checkout, or attempt payment.
   With the preview URL and server-side credentials available only in the
   operator's environment, run the focused boundary check from the web app:

   ~~~bash
   cd apps/storefront/web
   npx playwright test --config playwright.config.ts e2e/private-preview.spec.ts
   ~~~

7. From the Medusa service context, run node scripts/verify-live.mjs with the
   Ops URL, dedicated token and company ID, Medusa URL, publishable key, and
   STOREFRONT_TEST_SKU_ID available as environment variables. This checks the
   Ops response allowlist and Firstout→Medusa price and stock parity. Do not
   print or paste credential values into commands, screenshots, issue
   comments, or CI logs.
8. Record the generated hostname, UTC date, test SKU ID, HTTP status/header
   results, Ops/Medusa parity result, and a redacted browser screenshot in the
   issue evidence. Do not record credentials or tokens.

The health endpoint is a liveness check only. The Ops/Medusa parity script and
the protected browser walkthrough cover their dependencies. Do not claim the
hosted walkthrough is complete based on CI or /api/health alone.

## CI and local checks

Storefront TypeScript projects carry the existing platform:ts tag, so
Nx-affected CI runs lint, typecheck, and build for changed projects. This
change adds no deploy workflow or deploy manifest entry: deployment remains an
owner-controlled action after reviewing the private project. Before
provisioning, run the affected checks and verify both Dockerfiles build from
the repository root:

~~~bash
npx nx affected -t=lint,typecheck,build --base=origin/develop --head=HEAD
docker build -f apps/storefront/commerce/Dockerfile .
docker build -f apps/storefront/web/Dockerfile .
~~~

After provisioning, follow the hosted smoke sequence and record its results
before closing #759.

## Monthly cost hypothesis

This is a planning estimate using Railway's published Hobby resource rates,
not measured usage or a quote. It assumes one 730-hour preview environment
with low average resource use and no separate staging stack.

| Resource | Assumed average | Estimated monthly usage |
| --- | ---: | ---: |
| Web | 0.15 GB RAM, 0.04 vCPU | USD 2.30 |
| Medusa | 0.45 GB RAM, 0.08 vCPU | USD 6.10 |
| PostgreSQL | 0.30 GB RAM, 0.04 vCPU | USD 3.80 |
| Redis | 0.08 GB RAM, 0.02 vCPU | USD 1.20 |
| Postgres volume | 2 GB | USD 0.30 |
| Egress | 15 GB | USD 0.75 |
| **Estimated usage total** |  | **USD 14.45/month** |

The resource estimate applies USD 10/GB-month for memory, USD 20/vCPU-month,
USD 0.15/GB-month for the database volume, and USD 0.05/GB for egress. It is
**not an all-in Storefront forecast**. The following lines must be included
before claiming the USD 50/month target:

Railway's Hobby plan has a USD 5 monthly minimum that includes the first USD 5
of resource usage; it is not added to the table total. This estimate assumes
one replica per app service and no staging environment. Railway has no
project-only hard spending cap: per-service CPU/memory limits constrain
resource size, not the total bill. Set service limits after observing the
deployed peak; do not change workspace-wide controls for this project.

| Additional line | Private preview assumption | Remaining evidence |
| --- | --- | --- |
| Railway plan minimum and taxes | Existing workspace billing, no new plan purchase | Invoice treatment and marginal cost |
| Product media and object storage | Existing product URLs only; no new bucket yet | Storage/egress once media is provisioned |
| Database backups | No separate retention budget established | Retention policy and billed storage |
| Transactional email | Disabled for this preview | Provider plan and expected volume before launch |
| Clerk customer auth | Disabled for this preview | Development and production tier costs |
| PostHog EU analytics | Disabled for this preview | Consented event volume and plan cost |
| Monitoring and alerts | Railway health/logs only | Alerting plan and any external charge |
| Usage spikes and staging | No concurrent staging stack | Measured peak and any temporary staging days |

Confirm actual invoice treatment and record Railway's observed usage after a
representative month. Current product sync does not provision product media
storage. The estimate has not been verified against a provisioned service, and
workspace-level billing controls are not a project-level hard cap. Do not
claim the Storefront is under USD 50/month until every required line above is
measured or explicitly budgeted. If telemetry approaches the target, stop the
preview and review resource settings with the owner.

Pricing references: [Railway plans](https://docs.railway.com/pricing/plans),
[Railway resource pricing](https://railway.com/pricing), and
[Railway cost controls](https://docs.railway.com/pricing/cost-control).

## Rollback

This preview is isolated from Firstout and Marrow data. If a deployment fails,
revert the changed commit or select the last known-good Storefront deployment
in Railway; restore the previous web/Medusa image pair and verify both health
checks. If schema rollback is unsafe, roll forward from a database backup
instead of deleting or reusing the database. If the private boundary fails,
disable the web deployment or remove its generated hostname immediately, then
rotate the dedicated preview credentials and Ops token through their owners.
Never delete or modify Firstout, Marrow, or workspace-wide billing resources
as part of rollback.

## Evidence checklist

- [ ] Separate Railway project and environment verified; no shared data services.
- [ ] Web Basic Auth denies anonymous routes; only minimal health is public.
- [ ] No-index response header and page metadata verified.
- [ ] Medusa and web health checks pass.
- [ ] One real published SKU matches Ops price/availability and renders privately.
- [ ] No public DNS, live payment provider, bag/checkout, or test payment used.
- [ ] One-month Railway telemetry/invoice shows total under USD 50.
- [ ] Hostname, timestamp, test SKU, checks, and redacted screenshot recorded.

## Local production-image verification (2026-10-01)

The corrected commerce image was exercised as its non-root runtime user against
a separate disposable PostgreSQL database and Redis instance. Database migrations
passed from the compiled server directory; the compiled bootstrap script passed
twice consecutively. HTTP `/health` returned 200 `OK`, and `/app` returned 200
with the built admin HTML. Commerce typechecking passed, and the image-builder
test run passed 69 tests (four environment-gated tests skipped).

The production web image also built and ran locally with synthetic preview
credentials and the disposable commerce instance's publishable key. Anonymous
page, account API, and asset requests returned 401 with `no-store` and
`X-Robots-Tag: noindex, nofollow, noarchive`; the health probe returned 200.
Authenticated home, shop, collections, and account pages returned 200 with
private cache controls and the same robots header.

These checks prove the image can migrate and boot locally. They do not prove a
Railway deployment, Firstout SKU parity, provider interoperability, or the monthly
cost target. Those hosted acceptance items remain outstanding.
