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

On receive, blend unit cost at a location by quantity-weighted average: when adding stock to an existing `LocationStock` row, `new_cost = (old_on_hand × old_cost + incoming_qty × incoming_cost) / (old_on_hand + incoming_qty)`; if `old_on_hand` is 0 or `old_cost` is null, use the incoming cost.

The app does not send email.

## S5 prices

Endpoints: `PATCH /api/v1/skus/{id}` with optional `wholesale_ex_vat`, `wholesale_inc_vat`, `retail_ex_vat`, `retail_inc_vat`. Source of truth columns on `skus`: `wholesale_ex_vat`, `retail_ex_vat` only (ex-VAT stored; inc-VAT derived on read).

- **VAT:** 15% hardcoded (V1). Home currency **ZAR**. No SARS API.
- **Rounding:** store ex-VAT; display inc-VAT = `ex * 1.15` rounded half-up to the cent (`Decimal("0.01")`, `ROUND_HALF_UP`). Editing inc-VAT converts to ex-VAT with `inc / 1.15` rounded half-up to the cent.
- **Worked examples:** 100.00 ex → 115.00 inc; 2300.00 inc → 2000.00 ex; 2500.00 inc → 2173.91 ex.
- **Roles:** owner and buyer may PATCH prices; warehouse, till, and books may GET only (PATCH → 403).
- **Quotes:** out of V1 — no quote entity, table, or routes.

## S6 ledger (books)

Document-centric double-entry in ZAR. Every invoice, credit note, bill, and payment posts a balanced journal. Payments **record** cash/bank movement only — no PSP, EFT origination, or email.

**Seller particulars (tax invoice face):** Vellano, Kramerville, Johannesburg, South Africa, VAT 4123456789 (demo).

**Chart of accounts (seeded):**

| code | name | type |
|------|------|------|
| 1100 | Bank | asset |
| 1200 | Accounts receivable | asset |
| 1300 | Inventory | asset |
| 2100 | Accounts payable | liability |
| 2200 | VAT control | liability |
| 4000 | Sales | income |
| 5000 | Cost of goods sold | expense |
| 6100 | Foreign exchange gain/loss | expense |

**Numbering:** `INV-0001`, `CN-0001`, `BILL-0001`, `PAY-0001` (sequential, same algorithm as `PO-0001`).

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Accounts:** `GET/POST /accounts`, `PATCH /accounts/{id}` — list includes `balance_zar` (debits − credits on journal lines).
- **Contacts:** `GET/POST /contacts` — unified customers (`kind: customer`) and suppliers (`kind: supplier`). `POST` creates customers only; suppliers via `POST /suppliers`.
- **Invoices:** `GET/POST /invoices`, `GET /invoices/{id}`, `GET /invoices/{id}/pdf` — 15% VAT on face; journal Dr AR, Cr Sales + VAT control.
- **Credit notes:** `GET/POST /credit-notes`, `GET /credit-notes/{id}` — one CN per invoice; reverses AR/sales/VAT.
- **Bills:** `GET/POST /bills`, `GET /bills/{id}`, `POST/GET /bills/{id}/attachment` — foreign factory bills: no SA VAT; Dr Inventory, Cr AP. FX user-entered (`fx_to_zar` when currency ≠ ZAR).
- **Payments:** `GET/POST /payments` — `direction: in` (invoice, ZAR) or `out` (bill, foreign FX). Response includes `fx_gain_loss_zar` (positive = gain, negative = loss).

| Action | owner | buyer | warehouse | till | books |
|--------|:-----:|:-----:|:---------:|:----:|:-----:|
| List accounts, contacts, invoices, bills, payments | yes | yes | yes | yes | yes |
| Mutate CoA, contacts, invoices, CN, bills, payments | yes | no | no | no | yes |

Example invoice create:

```json
POST /api/v1/invoices
{
  "customer_id": "<uuid>",
  "issue_date": "2026-09-01",
  "lines": [{ "description": "Dining table", "qty": 1, "unit_ex_vat": "1000.00" }]
}
```

PDF: `GET /api/v1/invoices/{id}/pdf`

## S7 bank reconciliation, reports, VAT201 draft

Bank CSV import, payment matching, financial reports, and VAT201-shaped draft for manual eFiling entry. **Never** calls SARS or eFiling APIs.

### SA bank CSV column map

The importer accepts UTF-8 CSV with a header row. Column names are matched case-insensitively:

| Purpose | Accepted headers |
|---------|------------------|
| Date | `Date`, `Transaction Date`, `Posting Date`, `Value Date` |
| Description | `Description`, `Narrative`, `Details`, `Transaction Description` |
| Reference (optional) | `Reference`, `Ref`, `Transaction Reference` |
| Signed amount | `Amount`, `Transaction Amount`, `Signed Amount` — positive = money in, negative = money out |
| Debit / credit | `Debit` + `Credit` (or `Debit Amount` / `Credit Amount`) — credit minus debit |

Date formats: `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`. Either a signed **Amount** column **or** separate **Debit** and **Credit** columns is required.

Example fixture:

```csv
Date,Description,Reference,Amount
2026-09-02,Customer payment INV-0001,REF001,1150.00
2026-09-03,Supplier payment BILL-0001,REF002,-1800.00
2026-09-04,Unmatched deposit,REF003,500.00
```

### Endpoints (all under `/api/v1`, cookie `vellano_session`)

- **Bank imports:** `GET/POST /bank-imports`, `GET /bank-imports/{id}`, `GET /bank-imports/unmatched-lines`, `POST /bank-imports/{import_id}/lines/{line_id}/match` — body `{ "payment_id": "<uuid>" }`.
- **Reports:** `GET /reports/aged-ar?as_of=`, `GET /reports/aged-ap?as_of=`, `GET /reports/profit-loss?from=&to=`, `GET /reports/balance-sheet?as_of=`.
- **VAT201 draft:** `GET /reports/vat201?from=&to=`, `GET /reports/vat201/csv`, `GET /reports/vat201/pdf` — shaped fields for copy/type-in to eFiling only.

Matching a bank line sets `payments.is_reconciled = true`. Unmatched import lines remain visible. Amount+date suggestions are returned when a payment matches within ±3 days.

| Action | owner | buyer | warehouse | till | books |
|--------|:-----:|:-----:|:---------:|:----:|:-----:|
| List imports, reports, VAT201 draft | yes | yes | yes | yes | yes |
| Upload CSV, match lines | yes | no | no | no | yes |

## Railway (S11 — V1 deploy gate)

**Own Railway project** — not Marrow `zoological-fulfillment` (`a633a271-5bb0-461e-8eb5-1acb9e126a59`), not the Marrow develop environment, not Marrow Postgres/Redis/photos. Do not add `vellano-*` services to the Marrow project.

| Resource | ID / URL |
|----------|----------|
| Project `Vellano` | `c76d8df1-d839-454c-a94a-79b930deaf38` |
| Environment `develop` (active) | `7a8ce6f1-c514-4e5d-9c50-4b7918865321` |
| Environment `production` (empty) | `a639e365-f653-44db-a46d-a6a94e083894` — exists; **no** `vellano-api` / `vellano-frontend` config. Do not provision production. |
| Service `vellano-api` | `77a83033-b75e-4da1-88d0-b6db39bcedaf` |
| Service `vellano-frontend` | `10838be1-7a37-4dfc-810a-8805d040d5d7` |
| Postgres (own, not Marrow pgvector) | `a1a6695d-b8fb-4c79-92a6-664b48bc07e4` |
| API | https://vellano-dev-api.leo-figueiredo.com (`/api/v1/health`, Swagger `/docs`) — also https://vellano-api-develop-aba8.up.railway.app |
| Frontend | https://vellano-dev.leo-figueiredo.com — also https://vellano-frontend-develop-504f.up.railway.app |

- **Replicas:** 1 each (hobby tier, `sfo` region). No Redis. No extra services.
- **Config files:** `apps/vellano/{backend,frontend}/railway.toml` — no Root Directory; Config File path points here.
- **`watchPatterns`:** `apps/vellano/**` + imported libs (`libs/backend/core`, `db`, `storage` in backend toml). Live API service may omit `libs/backend/storage/**` until next redeploy; repo toml includes it.
- **Manifest:** `.github/deploy/manifest.yml` — `branches: [develop]` only. No `health_url.main`, no production.
- **Auth bootstrap:** on first deploy with empty `users`, seeds owner from `SEED_OWNER_EMAIL` / `SEED_OWNER_PASSWORD` (defaults `owner@example.com` / `change-me-owner`). Cookie `vellano_session` (HttpOnly, SameSite=Lax, Secure on HTTPS).
- **Develop env vars (`vellano-api`, names only):** `COOKIE_SECURE`, `CORS_ORIGINS`, `DATABASE_URL`, `JWT_SECRET`, `PORT`, `SEED_OWNER_EMAIL`, `SEED_OWNER_PASSWORD`. `DATABASE_URL` is the Vellano Postgres plugin, not Marrow `pgvector`.
- **Object storage:** develop `vellano-api` has no `BUCKET_NAME` / `AWS_*` — uploads use filesystem `STORAGE_DIR` fallback (not Marrow `photos` / `photos-dev`). **AC deviation from #510:** issue assumed a dedicated Railway bucket; not provisioned (no extra service). Wire a Vellano bucket later if uploads must survive redeploys.

## Non-goals

The app does not send email, pay, file VAT, or open a bank account. Auth (S1) is shipped — do not re-implement it. **S11** is the V1 deploy gate (Railway develop). Production Railway for Vellano is out of scope until a later epic.

## Python

`uv --project apps/vellano/backend`. **Never** create a root `uv.lock`. Python 3.10 only (`from __future__ import annotations`; no `X | Y`).

## PRs

Target `develop` only. Do not merge to `main` from this epic.
