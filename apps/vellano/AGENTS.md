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

It then creates these role users if the email is missing (idempotent; owner is never replaced):

| Email | Role | Password env | Default |
|-------|------|--------------|---------|
| `till@example.com` | till | `SEED_TILL_PASSWORD` | `change-me-till` |
| `books@example.com` | books | `SEED_BOOKS_PASSWORD` | `change-me-books` |
| `warehouse@example.com` | warehouse | `SEED_WAREHOUSE_PASSWORD` | `change-me-warehouse` |
| `buyer@example.com` | buyer | `SEED_BUYER_PASSWORD` | `change-me-buyer` |

Login requires `JWT_SECRET`. Cookie name is `vellano_session` (HttpOnly, SameSite=Lax, `Path=/`). Set `COOKIE_SECURE=true` when serving over HTTPS (Railway); leave `false` for local HTTP or the browser will not store the cookie.

Copy `apps/vellano/backend/.env.example` to `.env` and set a real `JWT_SECRET` before testing login locally.

### Permissions (F5)

Authorisation is a **permission catalog**, not role-tuple checks. `users.role` is a string slug matching `roles.slug`. Five built-in roles are **presets**. Owner is immutable (`is_system`, `is_owner_preset`); `has_permission` short-circuits for owner. Custom roles are named bundles (`POST /api/v1/roles`). Cookie remains `vellano_session`.

**Catalog** (`app/permissions.py`): `users.manage`, `settings.mutate`, `catalogue.mutate`, `po.raise`, `stock.receive`, `stock.transfer`, `stock.adjust`, `stock.cost.view`, `till.sell`, `till.discount`, `sales.returns`, `sales.laybys`, `sales.deliveries`, `sales.customers`, `books.mutate`, `books.journals`, `nia.use`, `nia.admin`.

| Preset | Keys |
|--------|------|
| **owner** | all catalog keys; cannot strip; cannot demote last owner |
| **buyer** | `catalogue.mutate`, `po.raise`, `stock.cost.view`, `nia.use` |
| **warehouse** | `stock.receive`, `stock.transfer`, `stock.adjust`, `sales.returns`, `sales.deliveries`, `nia.use` (no `stock.cost.view`, no till) |
| **till** | `till.sell`, `till.discount`, `sales.returns`, `sales.laybys`, `sales.deliveries`, `sales.customers`, `nia.use` (no `stock.cost.view`) |
| **books** | `books.mutate`, `books.journals`, `sales.customers`, `stock.cost.view`, `nia.use` (no `till.sell`) |

`GET /auth/me` returns `role` plus `permissions: list[str]`. Missing `stock.cost.view` nulls inventory `unit_cost_zar` and SKU `last_landed_cost_zar`; cost-audit is 403. Any till line `discount_percent > 0` requires `till.discount`.

Reads (list/get/PDF/reports) stay **any authenticated** unless noted. Mutate keys below replace the old owner\|warehouse\|… matrices.

### Nia (in-app assistant)

Product name is **Nia** — never “Copilot” in UI copy.

- **Stack:** PydanticAI + AG-UI on existing `vellano-api` (same cookie `vellano_session`). No CopilotKit, no extra Railway service, no Marrow `OPENROUTER_API_KEY`.
- **Permissions:** `nia.use` to talk to Nia; `nia.admin` to view/edit per-user token caps (owner preset includes both via all catalog keys).
- **Env on `vellano-api` (develop):** `OPENROUTER_API_KEY` (required for LLM), optional `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1` in app code). Health: `GET /api/v1/nia/health` → `{ok, llm}` (`llm` false if key missing). Do **not** add these to `vellano-frontend`.
- **Railway click-path:** Railway → project **Vellano** → service **vellano-api** → environment **develop** → Variables → `OPENROUTER_API_KEY`. Never copy Marrow `zoological-fulfillment` keys into git or this project.
- **Hard no:** Nia must not send email, take payment, or file with SARS/RCS.
- **Local:** ports remain `:8003` / `:3003`. Superdesign try-first for Nia UI (see [UI — IBM Carbon](#ui--ibm-carbon-explicit-exception-to-ui-kitmdc)).
- **Threads (N1):** `GET/POST /api/v1/nia/threads`, `GET /api/v1/nia/threads/{id}`, `POST /api/v1/nia/threads/{id}/archive` — require `nia.use`. List returns current user's non-archived threads only; cross-user GET is 404. Team-wide usage caps (`nia.admin`) are N5.
- **Run (N2):** `POST /api/v1/nia/threads/{id}/run` — require `nia.use`. Transport is **AG-UI SSE** via `pydantic_ai.ui.ag_ui.AGUIAdapter` (`streaming_response` + `run_stream`). Accepts either canonical AG-UI `RunAgentInput` JSON (`threadId`, `runId`, `messages`, `tools`, `context`, `forwardedProps`) or convenience JSON `{ "message": "…", "page": { "path": "/invoices" } }` (thread id from path; server generates `runId`). On completion: append user + assistant rows to the thread and insert a `nia_usage_events` row (`input_tokens`/`output_tokens` → prompt/completion). Missing `OPENROUTER_API_KEY` → **503** `{"detail":{"code":"nia_llm_unconfigured"}}` (never echo the key). `check_nia_budget` in `app/services/nia_caps.py` is a no-op until N5. CI/tests: `models.ALLOW_MODEL_REQUESTS = False` + `TestModel` override + dummy key.
- **HITL (N3):** deferred-tool approvals via `demo_echo_approval` (`requires_approval=True`). On `DeferredToolRequests`, persist `agent_messages` + `pending_tools` on the thread and append assistant text **"Nia needs your approval"** with `structured_payload` (never raw JSON in `content`). Card kinds: `needs_ok` (amber write — accept/decline/cancel), `your_call` (purple exclusive choice), `opened_page` (blue navigation). Resume: `POST /api/v1/nia/threads/{id}/resume` body `{ "decision": "accept"|"decline"|"cancel", "tool_call_id"? }` — missing pending → **409**; `cancel` clears pending and appends **"Cancelled."** (JSON 200, no model call); accept/decline resume via AG-UI SSE with `deferred_tool_results`. Alembic `038_nia_hitl` adds `pending_tools` + `agent_messages` JSONB on `nia_threads`. Tests: `tests/test_nia_hitl.py` — `TestModel(call_tools=['demo_echo_approval'])` forces approval; sequential `build_nia_model` patch for resume.
- **Tools (N4):** `app/nia/tools.py` — in-process wrappers around existing services (not HTTP self-calls). `NiaDeps` carries `db: AsyncSession` + permission keys. Tools: `navigate` (allowed paths from frontend `nav.ts` + `/canvas`), `search` (`SearchService`), `list_overdue_invoices` (30-day CRM clock), `get_stock_on_hand` (`InventoryService`; omits `unit_cost_zar` without `stock.cost.view`), `propose_transfer` (`TransferService.create` draft only). **Till cannot transfer** — `propose_transfer` returns a denial string (no HITL). Users with `stock.transfer` raise `ApprovalRequired` before create. `demo_echo_approval` unchanged. Tests: `tests/test_nia_tools_rbac.py` — `TestModel` / `FunctionModel` tool forcing.

### Playground seed (develop / local demos)

Env-gated, default **off**. When `SEED_PLAYGROUND=true`, startup creates a coherent demo path if it is not already present (markers: supplier `Playground Imports` / SKU `PG-TABLE`, then demo pack `PG-SOFA`, then sofa catalogue `VEL-SOFA-LONDON`):

suppliers + SKUs (ZAR, VAT 15%) → proforma PDF → PO → transit → land → receive 2 at Kramerville → two-step transfer 1 table to Bedfordview (draft → dispatch → receive) → customer invoice (paid) + till cash sale of that table → USD FX bill + 3-line bank CSV (two matched, one unmatched). A later pack adds high-end sofa SKUs with Unsplash photos (local files under `backend/data/playground_photos/`), extra customers, a trade invoice, a sofa layby, and a Minotti ZAR bill. Idempotent — existing DBs still get the sofa pack on the next boot.

**Railway develop:** on service `vellano-api`, set `SEED_PLAYGROUND=true` and redeploy (or restart). Safe to leave on — second boot is a no-op. Do not enable on a database you want to keep empty. After it runs, log in as `owner@example.com` / `change-me-owner` (or the role users above) and walk stock → proforma → PO → receive → transfer → till → books.

Local: `SEED_PLAYGROUND=true` in `apps/vellano/backend/.env`, then restart uvicorn.

## S2 locations

Endpoints: `GET/POST /api/v1/locations`, `PATCH /api/v1/locations/{id}`. Archive via `is_archived`; no DELETE.

| Action | Permission |
|--------|------------|
| List locations | any authenticated |
| Create / update / archive | `stock.receive` |

Startup seeds two locations when the table is empty: Kramerville (warehouse), Bedfordview (showroom). Same rows are inserted by migration `003_locations`.

## F0 warehouse bins

Bins are children of a location (row × bay × level). Quantity lives on `bin_stock`; `location_stock.on_hand` is always the rollup. **Unit cost stays on `location_stock.unit_cost_zar`** (weighted average) — no per-bin cost.

Every location has a default **FLOOR** bin (`code=FLOOR`, `row_code=F`, `bay=1`, `level=1`). Seed and `LocationService.create` add it; migration `029_warehouse_bins` backfills existing locations and copies `location_stock.on_hand` onto that bin.

- **API:** `GET/POST /locations/{id}/bins`, `POST /locations/{id}/bins/grid` (idempotent; skip existing row/bay/level), `PATCH /locations/{id}/bins/{bin_id}` (`is_archived` / `is_default`). Scan payload is bin `code`. List includes archived. Mutate: `stock.receive`. Read: any authenticated role.
- **Grid codes:** `{row}-{bay:02d}-{level}` e.g. `A-01-1`.
- **Print / scan:** bin labels via `printHtml` (blob URL + `window.open(url, "_blank")` — never `noopener`) + JsBarcode CODE128 of `code`. Receive/WMS type-or-scan matches `code` (case-insensitive).
- **Stock:** omitted `bin_id` / `from_bin_id` / `to_bin_id` uses the active default. Archived bins cannot receive. Cannot archive the default without assigning another first. Same-location bin-to-bin is out of v1.
- **Transfers:** optional `from_bin_id` / `to_bin_id` on each line; dest on-hand rises only on dest receive (F2).
- **Stocktake** stays location-scoped; variance applies to the default bin (no `stocktake_lines.bin_id`).

| Action | Permission |
|--------|------------|
| List bins | any authenticated |
| Create / grid / archive / set default | `stock.receive` |

## F2 two-step transfers

Internal stock move is a **document**, not a one-shot qty swap. Dest on-hand rises **only** on dest receive. In-app Transfer Note PDF (`GET /{id}/pdf`). **No email.**

Endpoints (cookie `vellano_session`): `GET/POST /api/v1/transfers`, `GET /transfers/{id}`, `POST /transfers/{id}/dispatch`, `GET /transfers/{id}/pdf`, `POST /transfers/{id}/receive`, `POST /transfers/{id}/cancel`.

Numbering: `TRF-0001`. Status: `draft` | `in_transit` | `received` | `cancelled`. Cancel is a status change (no DELETE).

- **Create draft** (`require_transfer` = `stock.transfer`): no stock movement. Same from/to → 400. Till cannot create or dispatch (403).
- **Dispatch:** draft → in_transit. Decrements **source** only (`apply_outgoing_qty`, bin or default). Does **not** increment dest. Captures dispatcher + timestamp and source `unit_cost_zar` on each line. Stocktake lock either end → 409. Over-qty / archived → 409.
- **Receive** (`require_transfer_receive` = `stock.transfer` or `till.sell`): v1 qty_received must equal qty_dispatched. Increments dest via `apply_incoming_qty` using the dispatch unit cost. Stamps receiver + `received_display_name`. Buyer/books → 403.
- **Cancel:** draft = `require_transfer`, no stock. in_transit = owner only, restock source. received = reject.

| Action | Permission |
|--------|------------|
| List / get / PDF | any authenticated |
| Create draft / dispatch | `stock.transfer` |
| Receive | `stock.transfer` or `till.sell` |
| Cancel draft | `stock.transfer` |
| Cancel in transit | `users.manage` |

Migration: `031_two_step_transfers`.

## Shop-floor qty patterns (A / B / C)

- **A carton_count**: same SKU ships in N cartons; qty is sellable units. Stock, till, PO qty, and books qty stay sellable. Packing sheet and invoice PDF may print a generated carton total when `carton_count > 1`.
- **B kit BOM**: virtual parent (`sku_bom_lines`); stock/pick are components. Till explodes the BOM: if **100% of every component** is at the posted showroom, consume there (F1). Otherwise `ConflictError("Kit requires pick")` unless a confirmed/picking/staged pick for the same kit×qty is posted (`pick_id` on the sale). Invoice is one line at the parent price. A SKU is a kit if it has ≥1 BOM line. Parent has no `on_hand` write on till.
- **C inner pack**: supplier carton of N eaches — **not in this ticket** (PO line later).

## V2-S2 stocktakes

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Stocktakes:** `GET/POST /stocktakes`, `GET /stocktakes/{id}`, `PATCH /stocktakes/{id}/lines/{line_id}` (`{counted_qty}` ≥ 0), `POST /stocktakes/{id}/lookup` (`{barcode}` exact `our_barcode`), `POST /stocktakes/{id}/complete`, `POST /stocktakes/{id}/cancel`. No pause endpoint.

Start snapshots **every SKU** at that location (`expected_qty` = on-hand or 0). Status `in_progress`. 409 if that location already has an in-progress stocktake.

**Location lock:** while `in_progress`, receive into the location, transfer from **or** to the location, and till sale at the location return 409 `"Location is locked for stocktake"`.

Complete only from `in_progress`. Lines with `counted_qty` set apply `delta = counted - expected` via stock movements (audit source `stocktake`); **uncounted lines are skipped** (on-hand unchanged). Then `completed` and unlock. Cancel only from `in_progress` → `cancelled`, no stock writes. No GL.

| Action | Permission |
|--------|------------|
| List / get stocktakes | any authenticated |
| Start, count, lookup, complete, cancel | `stock.receive` |

## V2-S3 stock adjustments

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Adjustments:** `GET/POST /adjustments`, `GET /adjustments/{id}`, `POST /adjustments/{id}/lines` (`{sku_id, qty_delta, unit_cost_zar?}`), `PATCH /adjustments/{id}/lines/{line_id}`, `DELETE /adjustments/{id}/lines/{line_id}` (204), `POST /adjustments/{id}/complete`, `POST /adjustments/{id}/cancel`.

Draft at a location; complete applies on-hand and one balanced journal. Reasons: `opening`, `damage`, `theft`, `count_fix`, `write_off`. Status: `draft` | `completed` | `cancelled`.

**qty_delta** (service): never 0. `opening` must be > 0; `damage` / `theft` / `write_off` must be < 0; `count_fix` any non-zero.

**GL by sign** (always; CoA includes **3000 Opening balances / equity**):

- Increases: Dr `1300` Inventory, Cr `3000` Opening balances
- Decreases: Dr `5000` COGS, Cr `1300` Inventory
- Mixed: both pairs when each total > 0 (skip a pair if that total is 0)

Create and complete return 409 `"Location is locked for stocktake"` while a stocktake is in progress at that location. Archived location → conflict. Cancel from `draft` only; no stock, no GL. `unit_cost_zar` required on complete for increases when location cost is missing, and for decreases when location cost is missing (`"unit cost required"`). Audit source `adjustment`.

| Action | Permission |
|--------|------------|
| List / get adjustments | any authenticated |
| Create, lines, complete, cancel | `stock.receive` |

## V2-S4 CSV import

Endpoints (cookie `vellano_session`): `POST /api/v1/imports/preview`, `POST /api/v1/imports/commit`. Multipart: `inventory` CSV required, `soh` CSV optional, optional JSON strings `inventory_map` / `soh_map`. No GET. **`catalogue.mutate`** (`require_catalogue_mutate`). Warehouse-only SOH import is deferred.

Preview is in-memory (200 even with row errors; 400 only if a file is unreadable or empty). Commit re-parses the files; any row error → 400; otherwise one transaction: inventory then SOH.

**Inventory columns:** our_ref, name, category, retail_inc_vat required; barcode and cost_zar optional. Category is required for Cin7 parity and **stored on the SKU** (`skus.category`, max 64). Create-or-update by exact `our_ref`. Create uses `design = csv:{our_ref}`, `fabric = -`, `our_barcode = barcode or csv:{our_ref}`. Retail inc-VAT is stored as `retail_ex_vat` via `inc_to_ex`.

**SOH columns:** our_ref, location, qty required; unit_cost_zar optional. Location is an active case-insensitive name match. SKU must exist in the DB or in the same inventory file. **SET** on-hand to qty (not add). Increase needs a unit cost from the SOH column, inventory `cost_zar`, or existing location cost (`"unit cost required to increase stock"`). Audit source `import`. In-progress stocktake at that location → 409 `"Location is locked for stocktake"`.

| Action | Permission |
|--------|------------|
| Preview / commit CSV import | `catalogue.mutate` |

## V2-S8 SKU category

- **SKUs:** nullable `category` (max 64) on create (`SkuCreate`), PATCH (`SkuUpdate` — set or clear with `null`), and in responses.
- **List filter:** `GET /skus?category=` — case-insensitive exact match when provided; omit to list all.
- **CSV import:** inventory `category` column is written on create and update (same as manual create).
- **Prices:** trade/wholesale = `wholesale_ex_vat`; retail = `retail_ex_vat` (S5, unchanged).

## V2-S9 till

- **Line discount:** optional `discount_percent` (0–100, default 0) per sale line; discounted unit price stored on the invoice line.
- **Tender:** `cash` | `card` | `deposit` — deposit records tender on `payments` only (Dr 1100 / Cr 1200, same as cash/card); no PSP, no 2300 (laybys own deposits).
- **VAT:** 15% on discounted ex-VAT subtotal (unchanged).
- **Returns:** process return is UI-only in S9; backend returns API unchanged (V2-S5).
- **Camera scan:** HTTPS (Railway) or localhost; type-in fallback if camera is denied.

## V2-S10 customers CRM

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Customers:** `GET/POST /customers`, `GET /customers/{id}`, `PATCH /customers/{id}`.

Extends the existing `customers` table (no second customer entity). Do **not** merge with `/contacts`. `POST /contacts` still creates ledger customers with CRM defaults; `ContactResponse` omits CRM fields.

**Columns:** `customer_type` (`retail` | `trade`, default `retail`), `price_tier` (default `standard`), `phone` (nullable), `credit_limit` (nullable Numeric 14,2), `on_hold` (bool, default false), `on_hold_reason` (nullable, 512).

**Aggregates** (computed, never stored overdue bit): `open_invoices_count`, `open_invoices_zar`, `overdue_invoices_count`, `overdue_invoices_zar`, `last_purchase_date` (`max(tax_invoices.issue_date)`), `active_laybys_count`, `active_laybys_zar`. Overdue clock is `issue_date + 30` (`as_of − 30 days`). Overdue is false when invoices are paid or no longer past terms. Do not change `GET /reports/aged-ar` math.

**List filters** (AND): `GET /customers?overdue=&active_layby=&on_hold=` — `overdue` = `overdue_invoices_count > 0`, `active_layby` = `active_laybys_count > 0`.

**Till / books credit gate:** named customer `on_hold` → 409 `"Customer is on hold"`; `credit_limit` set and `open_invoices_zar + sale/invoice total_inc_vat > credit_limit` → 409 `"Customer exceeds credit limit"`. Walk-in is skipped. Override keys on till (and books invoice create): `credit_override` + non-empty `credit_override_reason`. Override allowed only with `users.manage` OR `po.raise` (403 otherwise; 400 if override without reason). Audit on the invoice `books_events` CREATED row: `note` = `credit override: {reason}` (no new books action enum).

| Action | Permission |
|--------|------------|
| List / get customers | any authenticated |
| Create customers; PATCH name/phone/type/tier | `sales.customers` |
| PATCH `credit_limit` / `on_hold` / `on_hold_reason` | `users.manage` OR `po.raise` (till with only `sales.customers` → 403) |
| Till / invoice credit override | `users.manage` OR `po.raise` |

Migrations: `017_v2_s10_customers_crm`, `034_customer_credit`.

## V2-S13 SKU supplier prices

Extends `skus` (no second table). Columns: nullable `preferred_supplier_id` (FK `suppliers.id`, `ON DELETE SET NULL`), nullable `lead_time_days`. `supplier_ref` already exists — PATCH via `SkuUpdate` (set or clear with `null`).

`last_landed_cost_zar` is **computed** on read from the latest `unit_cost_audit` row for that SKU where `source` is `land` or `receive` only (opening, correction, import, etc. do not count). `SkuResponse` also includes `preferred_supplier_name` (lookup).

`PATCH /api/v1/skus/{id}` fields: identity (`our_ref`, `our_barcode`, `name`, `design`, `fabric`), `category`, `preferred_supplier_id`, `lead_time_days`, `supplier_ref`, plus price fields. Duplicate `our_ref` / `our_barcode` / design+fabric → 409. Unknown `preferred_supplier_id` → 404 `"Supplier not found"`. Null clears nullable fields via `model_fields_set`. Identity uniqueness checks pass `exclude_id` so unchanged values are not treated as collisions.

| Action | Permission |
|--------|------------|
| List / get SKUs (incl. supplier fields) | any authenticated (`last_landed_cost_zar` needs `stock.cost.view`) |
| PATCH supplier / lead time / supplier_ref | `catalogue.mutate` |

Migration: `018_v2_s13_sku_supplier`.

## V2-S11 deliveries

Fulfillment tracking only — till/layby already moved stock. **No stock movement. No journal.**

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Deliveries:** `GET/POST /deliveries`, `GET /deliveries/{id}`, `POST /deliveries/{id}/pack`, `POST /deliveries/{id}/complete` (optional `{delivery_date}`, default today), `POST /deliveries/{id}/cancel`.

Numbering: `DLV-0001`. Status: `draft` | `packed` | `delivered` | `cancelled`. Source: paid **invoice** (`amount_paid == total_inc_vat`) or non-cancelled **layby**. One non-cancelled delivery per source. Create copies all source lines (no client-supplied lines). Pack: draft → packed. Complete: packed → delivered. Cancel: draft only.

| Action | Permission |
|--------|------------|
| List / get deliveries | any authenticated |
| Create, pack, complete, cancel | `sales.deliveries` |

Migration: `019_v2_s11_deliveries`.

## V2-S12 reorder

Nullable `skus.reorder_min` (Integer). PATCH via `SkuUpdate` — set with `ge=1`, clear with `null`. Included on `SkuResponse`.

**Reorder math:** `on_hand` = SUM(`location_stock.on_hand`); `on_order` = (`sku_stock.on_order` or 0) + SUM(`po_lines.qty`) on purchase orders with status **`open`** (draft POs count; on-water qty lives in `sku_stock` only). Listed when `reorder_min IS NOT NULL` and `(on_hand + on_order) < reorder_min`. `suggested_qty = reorder_min - on_hand - on_order`.

Endpoints (cookie `vellano_session`):

- **Reorder:** `GET /reorder`, `POST /reorder/draft-po` body `{ sku_ids: [uuid, ...] }` (min 1).

`POST /reorder/draft-po` groups by `preferred_supplier_id`, one `PurchaseOrderService.create` per supplier (`proforma_id=null`, status `open`). Line `qty` = `suggested_qty`; `factory_unit_amount` = `last_landed_cost_zar` or `1`. Each SKU must be on the reorder list and have a preferred supplier.

| Action | Permission |
|--------|------------|
| GET reorder list | any authenticated |
| POST draft PO | `catalogue.mutate` |

Migration: `020_v2_s12_reorder_min`.

## V2-S14 mobile WMS

Frontend-only `/wms` warehouse console (no new API). Carbon ContentSwitcher: Receive | Count | Transfer. Wraps existing `POST /receive`, stocktake lookup/count/complete, and `POST /transfers`. Mutate: `stock.receive` / `stock.transfer`. Nav: Operations → WMS.

## V2-S15 reports (stock and sales)

Richer stock and sales reports under `/api/v1/reports` (cookie `vellano_session`). JSON + CSV export for each. All authenticated roles (same as existing S7 reports).

- **Stock valuation:** `GET /reports/stock-valuation`, `GET /reports/stock-valuation/csv` — on-hand &gt; 0 by location × SKU (`on_hand × unit_cost_zar`).
- **Aged stock:** `GET /reports/aged-stock`, `GET /reports/aged-stock/csv` — buckets `0-90`, `91-180`, `180+` days from `location_stock.updated_at` (180+ cutoff matches home `aged_stock_value_zar`).
- **Sales by SKU:** `GET /reports/sales-by-sku?from=&to=`, `GET /reports/sales-by-sku/csv` — invoice lines with non-null `sku_id` in date range (till + books). Books lines without `sku_id` are omitted.
- **Sales VAT summary:** `GET /reports/sales-vat?from=&to=`, `GET /reports/sales-vat/csv` — period totals from all `tax_invoices` (`invoice_count`, `subtotal_ex_vat`, `vat_amount`, `total_inc_vat`, `amount_paid`).

**No sales-by-location:** `tax_invoices` have no `location_id` — location-scoped sales reporting would need a schema change (out of scope).

| Action | Permission |
|--------|------------|
| All V2-S15 reports + CSV | any authenticated |

## V2-S5 returns / RMA

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Returns:** `GET/POST /returns`, `GET /returns/{id}`, `POST /returns/{id}/complete`, `POST /returns/{id}/cancel`.

Draft return against a tax invoice. Complete creates a **partial or full credit note** (one CN per invoice) and optionally restocks till-sale SKUs. Status: `draft` | `completed` | `cancelled`. Numbering: `RTN-0001`.

**Dispositions:** `restock` (till sales only — invoice lines must have `sku_id`) restores on-hand at `location_id` and posts COGS reverse (Dr 1300, Cr 5000) on the same CN journal. `write_off` posts CN sales reverse only (no stock movement).

One non-cancelled return per invoice. Cannot create if invoice already has a credit note. Cancel from `draft` only; no CN; a new return may then be created.

Complete restock while a stocktake is `in_progress` at that location → 409 `"Location is locked for stocktake"`.

| Action | Permission |
|--------|------------|
| List / get returns | any authenticated |
| Create / complete / cancel | `sales.returns` |

## V2-S6 laybys

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Laybys:** `GET/POST /laybys`, `GET /laybys/{id}`, `POST /laybys/{id}/payments`, `POST /laybys/{id}/complete`, `POST /laybys/{id}/cancel`.

Customer layaway with optional stock hold at a showroom. Numbering: `LB-0001`. Status: `open` | `ready` | `completed` | `cancelled` (overdue is derived from `due_date`, not stored).

**Deposits:** `layby_payments` table (not `payments`). GL Dr `1100` Bank, Cr `2300` Customer deposits on create and further payments. Account **2300** seeded via `ensure_customer_deposits()` and migration `014_v2_s6_laybys`.

**hold_stock=true:** showroom only; decrements on-hand at create (`UnitCostAuditSource.layby`); restocked on cancel; no second decrement on complete. **hold_stock=false:** on-hand unchanged until complete.

Complete (from `ready` only): tax invoice, Dr AR / Cr sales / Cr VAT; apply deposits Dr `2300` Cr AR; COGS Dr `5000` Cr `1300`; set `invoice_id`. Cancel: refund Dr `2300` Cr `1100` when `amount_paid > 0`.

Stocktake lock at location → 409 `"Location is locked for stocktake"` on hold create/cancel and on complete when not holding.

| Action | Permission |
|--------|------------|
| List / get laybys | any authenticated |
| Create, pay, complete, cancel | `sales.laybys` |

## V2-S7 home hub KPIs

`GET /home` (cookie `vellano_session`) extends the S10 summary with hub KPIs and attention lists. Existing fields (`on_order_*`, `on_hand_*`, `home_currency`) unchanged.

**KPI fields:** `aged_stock_value_zar` (on-hand value where `location_stock.updated_at` ≤ now−180 days), `open_laybys_count` / `open_laybys_balance_zar` (status `open`|`ready`), `low_stock_count` (SKUs with total on-hand 1–2 inclusive), `open_returns_count` (returns status `draft`).

**`needs_attention`** (max 8, skip empty groups): low-stock SKUs (3), in-progress stocktakes (2), draft returns, overdue laybys (`open` + `due_date` &lt; today), unmatched bank import lines.

**`recent_movements`** (max 10): newest `unit_cost_audit` rows — `source`, title (`sku.our_ref` or `note`), detail (`source` + location name when present), `created_at`.

| Action | Permission |
|--------|------------|
| Home summary | any authenticated |

## S3 catalogue (suppliers, proformas, SKUs)

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Suppliers:** `GET/POST /suppliers` — `{ name, default_currency? }` (currency defaults to USD).
- **Proformas:** `GET /proformas`, `POST /proformas` (multipart: `supplier_id`, `invoice_number`, `invoice_date`, optional `currency`, file field `file`), `GET /proformas/{id}`, `GET /proformas/{id}/file` (PDF).
- **SKUs:** `GET/POST /skus`, `GET /skus/{id}`, `PATCH /skus/{id}` (identity, category, prices, supplier fields), `DELETE /skus/{id}` (204; 409 if stock/orders/sales history), `POST /skus/{id}/photo` (field `photo`), `GET /skus/{id}/photo`.

**S1 opening stock:** optional on `POST /skus`: `opening_location_id`, `opening_qty` (≥ 1), `opening_unit_cost_zar` (> 0), `opening_date` (defaults to today). If any opening field is set, location, qty, and unit cost are required. Requires `catalogue.mutate`. Writes location on-hand and cost audit source `opening`; no GL. Unit-cost blend matches receive. Omit all opening fields for a catalogue-only create (SKU is not in `GET /inventory`). Catalogue-only SKUs can be `DELETE`d; SKUs with `location_stock`, orders, or sales history return 409 `"Cannot delete a SKU that has stock, orders, or sales history."`

UI labels distinguish **Our barcode** from **Supplier ref** — never conflate them.

| Action | Permission |
|--------|------------|
| List suppliers / proformas / catalogue | any authenticated |
| Create / update / delete SKU, file proforma, create supplier | `catalogue.mutate` |

No purchase orders, landed cost, quantities, or wholesale/retail pricing in S3.

## S4 purchase orders (PO, packing sheet, transit, land, receive)

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Purchase orders:** `GET/POST /purchase-orders`, `GET /purchase-orders/{id}`, `GET /purchase-orders/{id}/packing-sheet` (PDF), `POST /purchase-orders/{id}/on-water`, `POST /purchase-orders/{id}/land` (multipart: `fx_to_zar`, three bill fields + PDFs).
- **Receive:** `POST /receive` — JSON `purchase_order_id`, `location_id`.
- **Inventory:** `GET /inventory` — on-order, on-hand, sellable, unit costs per location.

| Action | Permission |
|--------|------------|
| List/get PO, packing sheet, inventory | any authenticated (inventory costs need `stock.cost.view`) |
| Create PO, on-water, land | `catalogue.mutate` |
| Receive | `stock.receive` |

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

## F7 actual lead times

Four nullable timestamptz stamps on `purchase_orders`: `ordered_at`, `on_water_at`, `landed_at`, `received_at`. First write wins (do not overwrite). Create sets `ordered_at` from `created_at` after flush. Migration `035_po_lead_timestamps` backfills `ordered_at` from `created_at` only — **never** invent water/land/received from `updated_at`. Historical received POs may only have `ordered_at`; prefer n=0 over fake days.

Reports (any authenticated — do **not** require `stock.cost.view`):

- `GET /api/v1/reports/supplier-lead-times` + `/csv`
- `GET /api/v1/reports/sku-lead-times` + `/csv`

Include only `status=received` with both `ordered_at` and `received_at`. Calendar days (`received_at.date() − ordered_at.date()`). **Median not mean** (`statistics.median`; `{10,20,100}` → 20). `median_last_3_days` is the median of the three newest by `received_at` (or all if n&lt;3). Multi-SKU POs share the same PO clock. `manual_lead_time_days` is read-only `Sku.lead_time_days` for comparison — **never PATCH** it from receive or reports. Do not change `#542` reorder math. All four stamps are on `PurchaseOrderResponse`.

## F8 SKU ABC / Pareto criticality

Revenue-based ABC on ex-VAT sales (`InvoiceLine.ex_vat`). **No Alembic.** Credit notes are **not** netted (#545 parity). Any authenticated — no `stock.cost.view`.

- `GET /api/v1/reports/sku-criticality?from=&to=` + `/csv` — optional `from`/`to` (same aliases as sales-by-sku); default last 12 calendar months through today inclusive.
- **A class** = cumulative value share ≤ 80% (value band, not top 20% of SKU count). **B** ≤ 95%, else **C**. `hits_50pct_band` marks the first SKU crossing 50% cumulative share. Header: `sku_count_for_50pct`, `sku_count_for_80pct`, `top_sku_share_pct`. Category rollup uses `Sku.category` (`null` → `Uncategorised`). Pure rank logic in `app/services/abc.py`.

## F9 multi-location kit pick

Location-scoped (not bin). No email. Reuse `stock.transfer` / `till.sell` / `sales.deliveries` — do **not** invent `picks.mutate`.

**Settings** (`team_settings`, Alembic `036_picks` revises `035_po_lead_timestamps`): `always_prefer_warehouse` (bool, default true), `pick_priority` (JSONB list of location UUID strings, default `[]` = derive). PATCH uses existing `settings.mutate`.

**Allocator** (`app/services/pick_allocator.py`, pure, no DB): walk `pick_priority` if set (skip missing/archived); else warehouse then showroom, `name` ASC within type. `always_prefer_warehouse` drains **all warehouse-type** locations first (not the name “Kramerville”). Never allocate more than on-hand or need. In-transit is already off `on_hand` (F2 dispatch) — no second ATP. Non-warehouse qty while warehouse has leftover the user skipped, or any non-warehouse qty while warehouse is short → `needs_confirm`. Shortfall is `qty_short`.

**Documents:** `picks` numbered `PCK-0001`; status `draft | confirmed | picking | staged | cancelled`; source `invoice | layby | till`. Lines + allocations. `transfers.pick_id` SET NULL.

**API** `/api/v1/picks`: GET list/get/pdf any authenticated. POST/PATCH/confirm/complete/cancel: any of `stock.transfer`, `till.sell`, `sales.deliveries`. Preview explodes F1 BOM, no persist, 400 if not a kit. Confirm requires full allocation; if `needs_confirm` and `confirm_split` is not true → 409 `"confirm_split required"`. Complete creates F2 transfers toward default staging (first warehouse in pick_priority / derived order — never a hardcoded UUID/name) and dispatches; dest on-hand rises only on receive. If every allocation is already at one showroom and `collect_from_showroom` (or all already at staging), skip transfers and set `staged`. One delivery (components, no stock move) when invoice/layby exists. Till-origin skips delivery until `invoice_id` is set. Receive of the last pick transfer sets `staged` and creates that delivery. Cancel draft/confirmed only.

**Till:** kit not 100% at the posted showroom and no matching pick → 409 `"Kit requires pick"` (do not decrement only Bedfordview). Matching pick: no showroom component decrement; set `pick.invoice_id`; COGS from allocation locations or showroom cost; missing cost → 409, do not steal stock.

v1 is location not bin.

## S5 prices

Endpoints: `PATCH /api/v1/skus/{id}` with optional `wholesale_ex_vat`, `wholesale_inc_vat`, `retail_ex_vat`, `retail_inc_vat`. Source of truth columns on `skus`: `wholesale_ex_vat`, `retail_ex_vat` only (ex-VAT stored; inc-VAT derived on read).

- **VAT:** 15% hardcoded (V1). Home currency **ZAR**. No SARS API.
- **Rounding:** store ex-VAT; display inc-VAT = `ex * 1.15` rounded half-up to the cent (`Decimal("0.01")`, `ROUND_HALF_UP`). Editing inc-VAT converts to ex-VAT with `inc / 1.15` rounded half-up to the cent.
- **Worked examples:** 100.00 ex → 115.00 inc; 2300.00 inc → 2000.00 ex; 2500.00 inc → 2173.91 ex.
- **Roles:** PATCH prices requires `catalogue.mutate`; GET is any authenticated role.
- **Quotes:** out of V1 — no quote entity, table, or routes.

## S6 ledger (books)

Document-centric double-entry in ZAR. Every invoice, credit note, bill, and payment posts a balanced journal. Payments **record** cash/bank movement only — no PSP, EFT origination, or email.

**Seller particulars (tax invoice face):** Vellano, Kramerville, Johannesburg, South Africa, VAT 4123456789 (demo).

**Chart of accounts (seeded):**

| code | name | type |
|------|------|------|
| 1100 | Bank (`is_bank`; default CSV recon) | asset |
| 1110 | Credit card (`is_bank`) | asset |
| 1120 | Petty cash (`is_bank`) | asset |
| 1130 | Inventory clearing (`is_bank`) | asset |
| 1140 | Supplier clearing (`is_bank`) | asset |
| 1200 | Accounts receivable | asset |
| 1300 | Inventory | asset |
| 2100 | Accounts payable | liability |
| 2200 | VAT control | liability |
| 2300 | Customer deposits | liability |
| 3000 | Opening balances | equity |
| 4000 | Sales (unmapped fallback) | income |
| 4010–4070 | Sales – Seating/Tables/Storage/Decor/Bedroom/Dining/Outdoor | income |
| 5000 | Cost of goods sold (unmapped fallback) | expense |
| 5010–5070 | COGS – same categories | expense |
| 5110–5170 | Stock adj – same categories | expense |
| 5210–5270 | Count var – same categories | expense |
| 6100 | Foreign exchange gain/loss | expense |

SKU `category` maps to those P&L accounts via `GET/PUT /api/v1/category-maps` (seeded; owner/books can upsert). Till/layby/adj/CN post to the mapped codes when the SKU has a category; books invoices without `sku_id` still use 4000. Extra accounts are added by `ensure_category_chart()` on startup.

**Numbering:** `INV-0001`, `CN-0001`, `BILL-0001`, `PAY-0001`, `JE-0001` (sequential, same algorithm as `PO-0001`).

Endpoints (all under `/api/v1`, cookie `vellano_session`):

- **Accounts:** `GET/POST /accounts`, `PATCH /accounts/{id}` — list includes `balance_zar` (debits − credits on posted journal lines), `tax_treatment` (`none` | `vat15`), and `is_bank`. Extra bank codes 1110–1140 are seeded by `ensure_bank_accounts()`.
- **Category maps:** `GET/PUT /category-maps` — SKU category → sales/COGS/stock-adj/count-var codes. Mutate: `books.mutate`.
- **Contacts:** `GET/POST /contacts` — unified customers (`kind: customer`) and suppliers (`kind: supplier`). `POST` creates customers only; suppliers via `POST /suppliers`.
- **Invoices:** `GET/POST /invoices`, `GET /invoices/{id}`, `GET /invoices/{id}/pdf` — 15% VAT on face; journal Dr AR, Cr Sales + VAT control.
- **Repeating invoices:** `GET/POST /repeating-invoices`, `GET/PATCH /repeating-invoices/{id}`, `POST /repeating-invoices/{id}/run` — run-now only (no cron, no email). Posted invoices have no draft status.
- **Credit notes:** `GET/POST /credit-notes`, `GET /credit-notes/{id}` — one CN per invoice; reverses AR/sales/VAT.
- **Bills:** `GET/POST /bills`, `GET /bills/{id}`, `POST/GET /bills/{id}/attachment` — foreign factory bills: no SA VAT; Dr Inventory, Cr AP. FX user-entered (`fx_to_zar` when currency ≠ ZAR).
- **Payments:** `GET/POST /payments` — `direction: in` (invoice, ZAR) or `out` (bill, foreign FX). Response includes `fx_gain_loss_zar` (positive = gain, negative = loss).
- **Journals:** `GET/POST /journals`, `GET /journals/{id}`, `POST /journals/{id}/post`, `POST /journals/{id}/void` — drafts excluded from CoA/P&L; void posts a reversing journal and keeps the original. Mutate: `books.mutate`.
- **Journal CSV (SimplePay):** `POST /journal-imports/preview` and `/commit` (multipart `file`); source `import:simplepay`; same-month 409. UI on `/journals`.
- **Books history:** append-only `GET /books-events?document_type=&document_id=` (`invoice` | `bill` | `payment` | `journal`). Journal post + void = two rows on the original id. No PATCH/DELETE.

| Action | Permission |
|--------|------------|
| List accounts, contacts, invoices, repeating invoices, bills, payments, journals | any authenticated |
| Mutate CoA, contacts, invoices, repeating invoices, CN, bills, payments, journals | `books.mutate` |

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

- **Bank imports:** `GET/POST /bank-imports`, `GET /bank-imports/{id}`, `GET /bank-imports/unmatched-lines`, `GET /bank-imports/unmatched-counts`, `POST /bank-imports/{import_id}/lines/{line_id}/match` — body `{ "payment_id" }` XOR `{ "journal_id" }`. Bank CSV is per recon account (`account_id` on `POST /bank-imports`; omit defaults to 1100). Bank rules (`GET/POST /bank-rules?bank_account_id=`, PATCH/DELETE `/{id}`) are confirm-to-apply (`POST .../apply-rule` `{ rule_id }`); recode journal-matched lines with `POST .../recode` `{ account_id }`.
- **Reports:** `GET /reports/aged-ar?as_of=`, `GET /reports/aged-ap?as_of=`, `GET /reports/profit-loss?from=&to=`, `GET /reports/balance-sheet?as_of=`, `GET /reports/trial-balance?as_of=`, `GET /reports/journals?from=&to=&source=` (source optional), `GET /reports/cash-summary?from=&to=` — plus `/csv` on trial-balance, journals, and cash-summary.
- **VAT201 draft:** `GET /reports/vat201?from=&to=`, `GET /reports/vat201/csv`, `GET /reports/vat201/pdf` — shaped fields for copy/type-in to eFiling only.
- **VAT201 periods:** `GET/POST /vat201/periods`, `GET /vat201/periods/{id}`, `POST .../lock` (`books.mutate`), `POST .../reopen` (`users.manage` + reason), `GET .../csv` and `/pdf`. Lock snapshots the VAT201 draft for that `from`/`to`. Range `GET /reports/vat201` stays for ad-hoc preview. Never SARS.

Matching a bank line to a payment sets `payments.is_reconciled = true`. Journal matches (manual JE or bank-rule apply) do not mark a payment. Unmatched import lines remain visible. Amount+date suggestions are returned when a payment matches within ±3 days. Per-account unmatched counts: `GET /bank-imports/unmatched-counts`.

| Action | Permission |
|--------|------------|
| List imports, reports, VAT201 draft | any authenticated |
| Upload CSV, match lines | `books.mutate` |

## Railway

**Own Railway project** — not Marrow `zoological-fulfillment`, not the Marrow develop environment, not Marrow Postgres/Redis/photos. Do not add `vellano-*` services to the Marrow project. Production has no Vellano services; the Marrow project has no Vellano config.

| Resource | ID / URL |
|----------|----------|
| Project `Vellano` | `c76d8df1-d839-454c-a94a-79b930deaf38` |
| Environment `develop` | `7a8ce6f1-c514-4e5d-9c50-4b7918865321` |
| Service `vellano-api` | `77a83033-b75e-4da1-88d0-b6db39bcedaf` |
| Service `vellano-frontend` | `10838be1-7a37-4dfc-810a-8805d040d5d7` |
| Postgres (own, not Marrow pgvector) | `a1a6695d-b8fb-4c79-92a6-664b48bc07e4` |
| Bucket `vellano-dev` (Tigris, develop only) | `49435225-4849-4132-bb87-66a23c67cdf1` |
| API | https://vellano-dev-api.leo-figueiredo.com (`/api/v1/health`, Swagger `/docs`) |
| Frontend | https://vellano-dev.leo-figueiredo.com |

- **Replicas:** 1 each (hobby tier, `sfo` region).
- **Config files:** `apps/vellano/{backend,frontend}/railway.toml` — no Root Directory; Config File path points here.
- **`watchPatterns`:** `apps/vellano/**` + `libs/backend/{core,db,storage}/**` (repo `railway.toml` and live `vellano-api`). Dockerfile `COPY`s `libs/backend/storage` for `f0rge_storage`.
- **Manifest:** `.github/deploy/manifest.yml` — `branches: [develop]` only. No `health_url.main`, no production.
- **Auth bootstrap:** on first deploy with empty `users`, seeds owner from `SEED_OWNER_EMAIL` / `SEED_OWNER_PASSWORD` (defaults `owner@example.com` / `change-me-owner`). Every startup also seeds missing role users `till@` / `books@` / `warehouse@` / `buyer@example.com` (`SEED_*_PASSWORD`, defaults `change-me-<role>`). Cookie `vellano_session` (HttpOnly, SameSite=Lax, Secure on HTTPS).
- **Playground dataset:** set `SEED_PLAYGROUND=true` on `vellano-api` and redeploy to fill catalogue / PO / till / books for demos. Default off. See [Playground seed](#playground-seed-develop--local-demos).
- **Object storage:** dedicated Railway Tigris bucket `vellano-dev` in this project only — never Marrow `photos` / `photos-dev`, never Marrow project buckets. On `vellano-api` develop: `BUCKET_NAME` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` reference `${{vellano-dev.*}}`; `AWS_ENDPOINT_URL_S3=https://fly.storage.tigris.dev`; `AWS_REGION=auto`. Keep `COOKIE_SECURE`, `JWT_SECRET`, `DATABASE_URL`. When those AWS vars are unset (local), uploads use `STORAGE_DIR`. Production is not wired.

## V2 shell (issue #530)

Superdesign canvas (try-first; record credits failure in PR if CLI blocks): [Vellano Back Office Home v2](https://superdesign.dev/teams/cb0bbbcd-2f7f-4810-9426-2fbdd5577264/projects/21ee8b12-d1ca-40c6-9b91-312aeb11a9f7) — draft `2d67462c-32c2-4baf-90c8-bdef3893e5bd`. Saved copy: `apps/vellano/frontend/.superdesign/v2-home.html`.

- **UI:** IBM Carbon only — never `@f0rge/ui`, Tailwind, shadcn, or Mantine in this app.
- **Chrome:** Carbon UIShell; content `g10`; SideNav dark via `Theme g100`; main offset `.vellano-main` **16rem expanded / 3rem collapsed** (`data-nav-expanded`).
- **Stub pages:** none remaining (Deliveries and Reorder shipped in V2-S11 / V2-S12).

V1 routes (stock, till, books, reports, VAT201, etc.) remain live. V2-S7 home hub KPIs and needs-attention / recent-movements tables ship on `/` via `GET /home`.

## Frontend routes vs API paths

Nav hrefs are not always the API prefix. When debugging network tabs:

| UI route | API prefix (`/api/v1`) |
|----------|------------------------|
| `/catalogue` | `/skus` |
| `/stock` | `/inventory` |
| `/ledger` | `/accounts`, `/category-maps` |
| `/journals` | `/journals`, `/journal-imports`, `/books-events` |
| `/contacts` | `/contacts` |
| `/invoices` | `/invoices`, `/books-events` |
| `/repeating-invoices` | `/repeating-invoices` |
| `/bills` | `/bills`, `/books-events` |
| `/payments` | `/payments`, `/books-events` |
| `/bank-reconciliation` | `/bank-imports`, `/bank-rules` |
| `/proformas` | `/proformas` |
| `/credit-notes` | `/credit-notes` |
| `/till` | `/till` |
| `/transfers` | `/transfers` |
| `/picks` | `/picks` |
| `/receive` | `/receive` |
| `/wms` | `/receive`, `/stocktakes`, `/transfers` |
| `/reports` | `/reports` |
| `/vat201` | `/vat201/periods` (range preview still `GET /reports/vat201`) |
| `/stocktakes` | `/stocktakes` |
| `/adjustments` | `/adjustments` |
| `/import` | `/imports` |
| `/returns` | `/returns` |
| `/laybys` | `/laybys` |
| `/customers` | `/customers` |
| `/deliveries` | `/deliveries` |
| `/reorder` | `/reorder` |

## Non-goals

The app does not send email (including repeating invoices), originate payments (PSP / EFT), file VAT with SARS, or open a bank account. Auth (S1) is shipped — do not re-implement it.

**In V1 (do not treat as future work):** locations, catalogue, proformas, POs, land/receive, prices, ledger, journals, repeating invoices, bank import (multi-account + rules), reports (incl. trial balance / journal / cash), VAT201 periods, books history, transfers, till, search, home, settings.

Still out of scope: production / `main`, Marrow, email, PSP charges, SARS eFiling, raising replicas above hobby 1.

## Python

`uv --project apps/vellano/backend`. **Never** create a root `uv.lock`. Python 3.10 only (`from __future__ import annotations`; no `X | Y`).

## PRs

Target `develop` only. Do not merge to `main` from this epic.
