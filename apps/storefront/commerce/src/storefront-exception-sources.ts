import type { IInventoryService, MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { availabilityMaxAgeMs } from "./checkout-holds";
import { readCapacityState } from "./made-to-order-capacity";
import { PEACH_ATTEMPTS_TABLE, PEACH_INBOX_TABLE, PEACH_REFUNDS_TABLE } from "./peach-payment-store";
import { peachPaymentEnabled } from "./peach-payment-config";
import { currentOpsCheckoutHealth, HANDOFF_AGED_THRESHOLD_MS, type StorefrontExceptionKind } from "./storefront-commerce-exceptions";

export const EXCEPTION_ACTIONS: Record<StorefrontExceptionKind, string> = {
  aged_hold: "release_expired_hold", stale_sync: "refresh_projection",
  missing_operational_paid_order: "retry_handoff", unknown_payment: "verify_with_provider",
  refund_mismatch: "reproject_verified_refund", fulfilment_drift: "resync_fulfillment",
  capacity_conflict: "acknowledge_capacity",
};
export type ExceptionObservation = {
  kind: StorefrontExceptionKind; correlation_id: string; status: "open" | "aged" | "terminal";
  explanation: string; safe_action: string; last_error?: string;
  provider_verified: boolean; blocks_checkout: boolean; detected_at: string;
  amount_minor?: number; payment_reference?: string;
};
export type ExceptionScan = { observed_at: string; observations: ExceptionObservation[] };
export function sourceRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function opsExceptionConnection() {
  const base = process.env.FIRSTOUT_OPS_URL;
  const token = process.env.FIRSTOUT_OPS_TOKEN;
  const company = process.env.FIRSTOUT_OPS_COMPANY_ID;
  if (!base || !token || !company) throw new Error("ops_connection_unconfigured");
  return { base: base.replace(/\/$/, ""), headers: {
    authorization: `Bearer ${token}`, "x-ops-company-id": company, "content-type": "application/json",
  } };
}

async function graphPages(container: MedusaContainer, entity: string, fields: string[]): Promise<Record<string, unknown>[]> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const rows: Record<string, unknown>[] = [];
  const seen = new Set<string>();
  for (let skip = 0; ; skip += 500) {
    const { data } = await query.graph({ entity, fields, pagination: { skip, take: 500, order: { id: "ASC" } } });
    if (!Array.isArray(data)) throw new Error("exception_graph_invalid");
    for (const value of data) {
      const row = sourceRecord(value);
      if (typeof row.id !== "string" || seen.has(row.id)) throw new Error("exception_scan_pagination_invalid");
      seen.add(row.id); rows.push(row);
    }
    if (data.length < 500) return rows;
  }
}

export async function peachSourceRows(db: Knex): Promise<{
  attempts: Record<string, unknown>[]; inbox: Record<string, unknown>[]; refunds: Record<string, unknown>[];
}> {
  const tables = [PEACH_ATTEMPTS_TABLE, PEACH_INBOX_TABLE, PEACH_REFUNDS_TABLE];
  const presence = await Promise.all(tables.map((table) => db.schema.hasTable(table)));
  // Disabled credentials cannot erase durable money failures. Only a provider
  // which never installed any tables can legitimately have no local sources.
  if (presence.every((exists) => !exists) && !peachPaymentEnabled()) return { attempts: [], inbox: [], refunds: [] };
  if (presence.some((exists) => !exists)) throw new Error("exception_peach_schema_incomplete");
  const rows: Record<string, unknown>[][] = [];
  for (const table of tables) {
    const result: Record<string, unknown>[] = [];
    let after = "";
    for (;;) {
      const page = await db<Record<string, unknown>>(table).whereNull("deleted_at").where("id", ">", after).orderBy("id").limit(500);
      result.push(...page);
      if (page.length < 500) break;
      const id = page.at(-1)?.id;
      if (typeof id !== "string" || id <= after) throw new Error("exception_scan_pagination_invalid");
      after = id;
    }
    rows.push(result);
  }
  return { attempts: rows[0], inbox: rows[1], refunds: rows[2] };
}

/** All reads must succeed before publishing: absent rows resolve live conditions in Ops. */
export async function collectStorefrontExceptionSources(container: MedusaContainer, fetcher: typeof fetch = fetch): Promise<ExceptionScan> {
  const observed = new Date();
  const now = observed.getTime();
  const scan: ExceptionScan = { observed_at: observed.toISOString(), observations: [] };
  const add = (kind: StorefrontExceptionKind, id: string, explanation: string, at: unknown, extra: Partial<ExceptionObservation> = {}) => {
    const parsed = new Date(String(at)).getTime();
    scan.observations.push({ kind, correlation_id: `storefront:${kind}:${id}`, status: "open", explanation,
      safe_action: EXCEPTION_ACTIONS[kind], provider_verified: false, blocks_checkout: false,
      detected_at: new Date(Number.isFinite(parsed) ? Math.min(parsed, now) : now).toISOString(), ...extra });
  };
  const inventory = container.resolve<IInventoryService>(Modules.INVENTORY);
  for (let skip = 0; ; skip += 500) {
    const page = await inventory.listReservationItems({}, { skip, take: 500, order: { id: "ASC" } });
    for (const row of page) {
      const metadata = sourceRecord(row.metadata);
      if (row.created_by?.startsWith("storefront_hold:") && Date.parse(String(metadata.expires_at)) <= now) {
        add("aged_hold", row.id, "Expired checkout inventory reservation remains allocated.", metadata.expires_at, { status: "aged" });
      }
    }
    if (page.length < 500) break;
  }
  const variants = await graphPages(container, "product_variant", ["id", "metadata", "product.status"]);
  const sourceVariants = variants.filter((row) => sourceRecord(row.metadata).source_sku_id);
  const projected = sourceVariants.filter((row) => sourceRecord(row.product).status === "published");
  const stale = projected.filter((row) => {
    const timestamp = Date.parse(String(sourceRecord(row.metadata).source_observed_at));
    return !Number.isFinite(timestamp) || now - timestamp > availabilityMaxAgeMs();
  });
  if (!sourceVariants.length || stale.length || (!currentOpsCheckoutHealth().opsReachable && currentOpsCheckoutHealth().lastProjectionAt)) add("stale_sync", "projection", "Operational stock projection is missing or stale.",
    stale[0] ? sourceRecord(stale[0].metadata).source_observed_at : observed, { status: "aged", blocks_checkout: true });
  for (const variant of variants) {
    for (const allocation of Object.values(readCapacityState(sourceRecord(variant.metadata)).allocations)) {
      for (const [key, hold] of Object.entries(allocation.holds)) {
        if (Date.parse(hold.expires_at) <= now) add("aged_hold", `${variant.id}:${key}`, "Expired finite made-to-order capacity remains held.", hold.expires_at, { status: "aged" });
      }
    }
  }
  const orders = await graphPages(container, "order", ["id", "created_at", "metadata", "payment_collections.payments.captured_at"]);
  const orderIds = new Set(orders.map((row) => row.id));
  const paidOrders = orders.filter((order) => {
    if (!sourceRecord(order.metadata).storefront_confirmation_sha256) return false;
    const collections = Array.isArray(order.payment_collections) ? order.payment_collections : [];
    return collections.some((value) => {
      const payments = sourceRecord(value).payments;
      return Array.isArray(payments) && payments.some((payment) => !!sourceRecord(payment).captured_at);
    });
  });
  const connection = opsExceptionConnection();
  const receipts = new Map<string, string>();
  for (let skip = 0; skip < paidOrders.length; skip += 500) {
    const ids = paidOrders.slice(skip, skip + 500).map((row) => String(row.id));
    const response = await fetcher(`${connection.base}/orders/status`, { method: "POST", headers: connection.headers,
      body: JSON.stringify({ external_order_ids: ids }), signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error(`exception_order_status_http_${response.status}`);
    const body = sourceRecord(await response.json());
    if (!Array.isArray(body.items) || body.items.length !== ids.length) throw new Error("exception_order_status_incomplete");
    const remaining = new Set(ids);
    for (const value of body.items) {
      const row = sourceRecord(value);
      if (typeof row.external_order_id !== "string" || !remaining.delete(row.external_order_id) ||
          !["imported", "missing", "stock_conflict", "failed"].includes(String(row.status))) throw new Error("exception_order_status_invalid");
      receipts.set(row.external_order_id, String(row.status));
    }
    if (remaining.size) throw new Error("exception_order_status_incomplete");
  }
  for (const order of orders) {
    const metadata = sourceRecord(order.metadata);
    if (!metadata.storefront_confirmation_sha256) continue;
    const collections = Array.isArray(order.payment_collections) ? order.payment_collections : [];
    const paid = collections.some((value) => {
      const payments = sourceRecord(value).payments;
      return Array.isArray(payments) && payments.some((payment) => !!sourceRecord(payment).captured_at);
    });
    if (!paid) continue;
    const outbox = sourceRecord(metadata.storefront_handoff_outbox);
    if (outbox.status !== "imported" || receipts.get(String(order.id)) !== "imported") {
      const created = outbox.created_at || order.created_at;
      add("missing_operational_paid_order", String(order.id), "Captured native order has not been accepted by operations.", created, {
        status: ["failed", "stock_conflict"].includes(String(outbox.status)) ? "terminal"
          : now - Date.parse(String(created)) >= HANDOFF_AGED_THRESHOLD_MS ? "aged" : "open",
        provider_verified: true, ...(typeof outbox.failure_code === "string" ? { last_error: outbox.failure_code.slice(0, 255) } : {}),
      });
    }
    const capacity = sourceRecord(metadata.storefront_capacity_exception);
    if (capacity.status === "paid_exception") add("capacity_conflict", String(order.id), "Captured order's finite capacity or handoff commitment needs recovery.", capacity.recorded_at,
      { status: "terminal", provider_verified: true, blocks_checkout: true });
  }
  const db = container.resolve<Knex>(ContainerRegistrationKeys.PG_CONNECTION);
  const peach = await peachSourceRows(db);
  const attempts = new Map(peach.attempts.map((row) => [row.merchant_reference, row]));
  const money = (row: Record<string, unknown>): Partial<ExceptionObservation> => {
    const amount = Number(row.amount_minor);
    return { ...(Number.isSafeInteger(amount) && amount > 0 ? { amount_minor: amount } : {}),
      ...(typeof row.merchant_reference === "string" ? { payment_reference: row.merchant_reference.slice(0, 128) } : {}) };
  };
  for (const row of peach.attempts) {
    if (row.status === "captured" && (!row.captured_order_id || !orderIds.has(row.captured_order_id))) {
      add("missing_operational_paid_order", String(row.id), "Verified external payment has no surviving native order; original payment and checkout binding are retained.", row.created_at,
        { status: "terminal", provider_verified: true, blocks_checkout: true, ...money(row) });
    } else if (["unknown", "initiation_unknown"].includes(String(row.status)) ||
        (["initiating", "pending", "checkout_created"].includes(String(row.status)) && now - Date.parse(String(row.created_at)) >= HANDOFF_AGED_THRESHOLD_MS)) {
      add("unknown_payment", String(row.id), "Payment outcome remains unknown; reconcile with the provider before repeating or repairing it.", row.created_at,
        { status: "aged", blocks_checkout: true, ...money(row) });
    }
  }
  for (const row of peach.inbox) {
    const attempt = attempts.get(row.merchant_reference);
    if (row.status === "paid_exception" && (!attempt?.captured_order_id || !orderIds.has(attempt.captured_order_id))) {
      if (attempt?.status !== "captured") add("missing_operational_paid_order", String(row.id), "Verified paid callback needs recovery; its original binding may be unavailable.", row.created_at,
        { status: "terminal", provider_verified: true, blocks_checkout: true, ...money(row) });
    }
    if (row.payment_type === "RF" && ["needs_review", "retry"].includes(String(row.status))) {
      add("refund_mismatch", String(row.id), "Verified refund callback has not converged into operational and native refund state.", row.created_at,
        { status: "terminal", provider_verified: row.source !== "webhook" || !!row.signature_sha256, ...money(row) });
    }
  }
  for (const row of peach.refunds) {
    if (["unknown", "needs_review", "verified", "recording_medusa_refund"].includes(String(row.status)) ||
        (row.status === "succeeded" && (!row.medusa_refund_id || row.firstout_status !== "succeeded"))) {
      add("refund_mismatch", String(row.request_id), "Durable refund outcome has not converged into both operations and native money state.", row.created_at,
        { status: "terminal", provider_verified: !!row.canonical_sha256 && !!row.provider_refund_id, ...money(row) });
    }
  }
  const feed = await fetcher(`${connection.base}/fulfillment-events?limit=100`, { headers: connection.headers, cache: "no-store", signal: AbortSignal.timeout(10000) });
  if (!feed.ok) throw new Error(`exception_fulfillment_feed_http_${feed.status}`);
  const body = sourceRecord(await feed.json());
  if (!Array.isArray(body.items)) throw new Error("exception_fulfillment_feed_invalid");
  // This represents the entire durable backlog, not the first page's identities.
  // It stays present until Ops returns an empty pending feed after real acks.
  if (body.items.length) add("fulfilment_drift", "pending-feed", "Operational fulfillment changes remain unapplied or unacknowledged in commerce.", sourceRecord(body.items[0]).occurred_at);
  if (scan.observations.length > 10000) throw new Error("exception_scan_too_large");
  return scan;
}
