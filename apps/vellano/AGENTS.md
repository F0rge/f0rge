# Vellano — Agent Instructions

Gauteng furniture retailer back office (stock, books, till). Sibling app next to Marrow and dk. **Never** nest this under `apps/marrow/`. **Never** a new repo.

Owner routing (even though `.cursor/rules/orchestration.mdc` still lists marrow paths):

| Area | Sub-agent |
|------|-----------|
| `apps/vellano/backend` | `fastapi-backend` |
| `apps/vellano/frontend` | `frontend-dev` |
| Nx / Docker / Railway / `.github/deploy` | `devops` |

Read `~/.cursor/agent-memory/<agent>/MEMORY.md` first. Write gotchas back when done.

## UI — IBM Carbon (explicit exception to `ui-kit.mdc`)

- **This app uses IBM Carbon (`@carbon/react`, `@carbon/styles`, `@carbon/icons-react`).**
- Do **not** import `@f0rge/ui`, `@f0rge/ui/forms`, or `@f0rge/ui/api`.
- Do **not** put Carbon in `libs/ui`. Do **not** run `add-ui-primitive` for Vellano.
- `ui-kit.mdc` remains the default for Marrow and dk. This nested AGENTS.md is the exception.
- Superdesign: try the Superdesign plugin first for frontend/UI. If the CLI reports credits/quota/paywall/auth failure, skip the canvas, implement Carbon, and record that in the PR. Do not invent extra retries.

## Stack

- Backend: FastAPI Python 3.10 + async SQLAlchemy + asyncpg + Alembic. API prefix `/api/v1`.
- Frontend: Next.js App Router `output: 'standalone'`.
- Auth cookie (S1, not S0): `vellano_session` — **not** `ht_session`.
- Import only: `f0rge_core`, `f0rge_db`, `f0rge_storage`, `f0rge_testing`. No Vellano domain in shared libs.

## Local ports (locked)

| Service | Port |
|---------|------|
| API | `:8003` |
| Frontend | `:3003` |
| Postgres | `:5433` |

Do not use Marrow `:8000/:3000` or dk `:8002/:3002`.

## Own database

```bash
cd apps/vellano && docker compose up -d postgres
```

`DATABASE_URL=postgresql+asyncpg://vellano:vellano@localhost:5433/vellano`

**Never** reuse Marrow `DATABASE_URL`, `ht-postgres`, Railway `pgvector`, Redis, or the photos bucket.

## Running

```bash
cd apps/vellano && docker compose up -d postgres
cd apps/vellano/backend && uv run uvicorn app.main:app --port 8003 --reload
cd apps/vellano/frontend && npm run dev   # :3003, rewrites /api/* → :8003
```

### S1 auth bootstrap

On startup, if the `users` table is empty the API seeds one team (`Vellano`) and one owner from env:

- `SEED_OWNER_EMAIL` (default `owner@example.com`)
- `SEED_OWNER_PASSWORD` (default `change-me-owner`)

Login requires `JWT_SECRET`. Cookie name is `vellano_session` (HttpOnly, SameSite=Lax, `Path=/`). Set `COOKIE_SECURE=true` when serving over HTTPS (Railway); leave `false` for local HTTP or the browser will not store the cookie.

Copy `apps/vellano/backend/.env.example` to `.env` and set a real `JWT_SECRET` before testing login locally.

## S2 locations

Endpoints: `GET/POST /api/v1/locations`, `PATCH /api/v1/locations/{id}`. Archive via `is_archived`; no DELETE.

| Action | owner | warehouse | buyer | till | books |
|--------|:-----:|:---------:|:-----:|:----:|:-----:|
| List locations | yes | yes | yes | yes | yes |
| Create / update / archive | yes | yes | no | no | no |

Startup seeds two locations when the table is empty: Kramerville (warehouse), Bedfordview (showroom). Same rows are inserted by migration `003_locations`.

## S3 catalogue (suppliers, proformas, SKUs)

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Suppliers:** `GET/POST /suppliers` — `{ name, default_currency? }` (currency defaults to USD).
- **Proformas:** `GET /proformas`, `POST /proformas` (multipart: `supplier_id`, `invoice_number`, `invoice_date`, optional `currency`, file field `file`), `GET /proformas/{id}`, `GET /proformas/{id}/file` (PDF).
- **SKUs:** `GET/POST /skus`, `POST /skus/{id}/photo` (field `photo`), `GET /skus/{id}`, `GET /skus/{id}/photo`.

UI labels distinguish **Our barcode** from **Supplier ref** — never conflate them.

| Action | owner | buyer | warehouse | till | books |
|--------|:-----:|:-----:|:---------:|:----:|:-----:|
| List suppliers / proformas / catalogue | yes | yes | yes | yes | yes |
| Create supplier / file proforma / add SKU | yes | yes | no | no | no |

No purchase orders, landed cost, quantities, or wholesale/retail pricing in S3.

## S4 purchase orders (PO, packing sheet, transit, land, receive)

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Purchase orders:** `GET/POST /purchase-orders`, `GET /purchase-orders/{id}`, `GET /purchase-orders/{id}/packing-sheet` (PDF), `POST /purchase-orders/{id}/on-water`, `POST /purchase-orders/{id}/land` (multipart: `fx_to_zar`, three bill fields + PDFs).
- **Receive:** `POST /receive` — JSON `purchase_order_id`, `location_id`.
- **Inventory:** `GET /inventory` — on-order, on-hand, sellable, unit costs per location.

| Action | owner | buyer | warehouse | till | books |
|--------|:-----:|:-----:|:---------:|:----:|:-----:|
| List/get PO, packing sheet, inventory | yes | yes | yes | yes | yes |
| Create PO, on-water, land | yes | yes | no | no | no |
| Receive | yes | no | yes | no | no |

PO numbers are sequential `PO-0001` (our ref, not supplier). Optional `proforma_id` must match PO supplier.

**Landed cost allocation (value-weighted by factory line):**

1. Convert factory, freight, and clearance **bill amounts** to ZAR. If a bill's currency is `ZAR`, use the amount as-is. Otherwise multiply by `fx_to_zar` (ZAR per 1 unit of that currency).
2. Each PO line has `factory_unit_amount` (supplier/factory currency) and `qty`. Line weight = `qty * factory_unit_amount` (must be > 0).
3. `line_share = line_weight / sum(line_weights)`.
4. `line_landed_zar = line_share * (factory_zar + freight_zar + clearance_zar)`.
5. `unit_cost_zar = line_landed_zar / qty` — must be a positive Decimal.

Factory bills default to `supplier.default_currency` (else USD). Freight/clearance store currency per bill. Home currency ZAR. Inventory unit cost lives on received units / location stock. `sellable` is true only when `on_hand > 0` (on-order is never sellable).

The app does not send email.

## Railway

**Own Railway project** — not Marrow `zoological-fulfillment`, not the Marrow develop environment, not Marrow Postgres/Redis/photos. Do not add `vellano-*` services to the Marrow project.

- Project: `Vellano` (`c76d8df1-d839-454c-a94a-79b930deaf38`)
- Environment: `develop` only (`7a8ce6f1-c514-4e5d-9c50-4b7918865321`)
- Frontend: https://vellano-dev.leo-figueiredo.com
- API: https://vellano-dev-api.leo-figueiredo.com (`/api/v1/health`, Swagger `/docs`)
- Config files: `apps/vellano/{backend,frontend}/railway.toml` (no Root Directory)
- `watchPatterns` = `apps/vellano/**` + libs actually imported
- Manifest: `branches: [develop]` only. No production, no `main`

## Non-goals

The app does not send email, pay, file VAT, or open a bank account. Auth (S1) is shipped — do not re-implement it. Out of scope: ledger, till, and other S5–S11 product features.

## Python

`uv --project apps/vellano/backend`. **Never** create a root `uv.lock`. Python 3.10 only (`from __future__ import annotations`; no `X | Y`).

## PRs

Target `develop` only. Do not merge to `main` from this epic.
