import { randomUUID } from "node:crypto";
import type { ILockingModule, MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { expireCheckoutHolds } from "./checkout-holds";
import { syncFirstout } from "./sync-firstout";
import { retryStorefrontOrderHandoff } from "./storefront-order-handoff";
import { syncStorefrontFulfillmentEvents } from "./storefront-fulfillment-events";
import { reconcilePeachCheckoutStatuses } from "./peach-webhook-processing";
import { completePeachWebhook, PEACH_INBOX_TABLE, type PeachInboxEvent } from "./peach-payment-store";
import { processClaimedPeachRefundWebhook, reconcileVerifiedMedusaRefunds } from "./storefront-peach-refunds";
import { collectStorefrontExceptionSources, EXCEPTION_ACTIONS, opsExceptionConnection, peachSourceRows, sourceRecord, type ExceptionScan } from "./storefront-exception-sources";
import type { StorefrontExceptionKind } from "./storefront-commerce-exceptions";

export type ExceptionCommand = { id: string; correlation_id: string; kind: StorefrontExceptionKind; action: string; idempotency_key: string };
function commands(value: unknown): ExceptionCommand[] {
  const items = sourceRecord(value).items;
  if (!Array.isArray(items)) throw new Error("exception_commands_invalid");
  return items.map((value) => {
    const row = sourceRecord(value);
    if (typeof row.kind !== "string" || !(row.kind in EXCEPTION_ACTIONS) || typeof row.id !== "string" ||
        typeof row.correlation_id !== "string" || typeof row.idempotency_key !== "string" ||
        row.action !== EXCEPTION_ACTIONS[row.kind as StorefrontExceptionKind] ||
        !row.correlation_id.startsWith(`storefront:${row.kind}:`)) throw new Error("exception_command_invalid");
    return row as ExceptionCommand;
  });
}
async function opsRequest(path: string, fetcher: typeof fetch, body?: unknown): Promise<unknown> {
  const connection = opsExceptionConnection();
  const response = await fetcher(`${connection.base}/${path}`, { method: body === undefined ? "GET" : "POST",
    headers: connection.headers, cache: "no-store", ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`exception_ops_http_${response.status}`);
  return response.json();
}
async function publish(scan: ExceptionScan, fetcher: typeof fetch): Promise<void> {
  const response = sourceRecord(await opsRequest("exceptions/observations", fetcher, scan));
  if (response.accepted !== true) throw new Error("exception_scan_not_accepted");
}
async function repairRefund(container: MedusaContainer, sourceId: string, fetcher: typeof fetch): Promise<void> {
  const db = container.resolve<Knex>(ContainerRegistrationKeys.PG_CONNECTION);
  const sources = await peachSourceRows(db);
  const dispatch = sources.refunds.find((row) => row.request_id === sourceId);
  const event = sources.inbox.find((row) => row.payment_type === "RF" && (row.id === sourceId ||
    row.refund_request_id === sourceId || (dispatch?.provider_refund_id && row.transaction_id === dispatch.provider_refund_id)) &&
    (row.source === "refund-response" || (row.source === "webhook" && !!row.signature_sha256)));
  if (event) {
    // Re-lease a retained verified observation; no new provider refund is dispatched.
    const claimed: PeachInboxEvent | undefined = await db.transaction(async (trx) => {
      const row = await trx<PeachInboxEvent>(PEACH_INBOX_TABLE).where({ id: event.id }).whereNull("deleted_at").forUpdate().first();
      if (!row || (row.status === "processing" && row.lease_until && new Date(row.lease_until) > new Date())) return undefined;
      const token = randomUUID();
      const updated = { ...row, status: "processing", lease_token: token, lease_until: new Date(Date.now() + 120000) };
      await trx(PEACH_INBOX_TABLE).where({ id: row.id }).update({ status: updated.status, lease_token: token, lease_until: updated.lease_until, updated_at: new Date() });
      return updated;
    });
    if (!claimed) throw new Error("refund_recovery_lease_active");
    try {
      const outcome = await processClaimedPeachRefundWebhook(container, db, claimed, fetcher);
      await completePeachWebhook(db, claimed.id, claimed.lease_token, outcome === "needs_review" ? "needs_review" : "processed");
    } catch (error) {
      await completePeachWebhook(db, claimed.id, claimed.lease_token, "needs_review");
      throw error;
    }
  } else if (dispatch?.canonical_sha256 && dispatch.provider_refund_id && ["verified", "recording_medusa_refund"].includes(String(dispatch.status))) {
    await reconcileVerifiedMedusaRefunds(container, db, sourceId);
  } else throw new Error("refund_requires_verified_provider_observation");
}
async function executeRepair(container: MedusaContainer, command: ExceptionCommand, fetcher: typeof fetch): Promise<void> {
  const sourceId = command.correlation_id.slice(`storefront:${command.kind}:`.length);
  switch (command.kind) {
    case "aged_hold": await expireCheckoutHolds(container); return;
    case "stale_sync": await syncFirstout(container); return;
    case "missing_operational_paid_order":
    case "capacity_conflict":
      if (!sourceId.startsWith("order_")) throw new Error("captured_payment_requires_native_order_recovery");
      await retryStorefrontOrderHandoff(container, sourceId, true); return;
    case "unknown_payment": {
      const db = container.resolve<Knex>(ContainerRegistrationKeys.PG_CONNECTION);
      const row = (await peachSourceRows(db)).attempts.find((row) => row.id === sourceId);
      if (typeof row?.payment_session_id !== "string") throw new Error("payment_recovery_source_missing");
      await reconcilePeachCheckoutStatuses(container, row.payment_session_id); return;
    }
    case "refund_mismatch": await repairRefund(container, sourceId, fetcher); return;
    case "fulfilment_drift":
      for (let page = 0; page < 100; page += 1) {
        const result = await syncStorefrontFulfillmentEvents(container, fetcher);
        if (!result.received || !result.acknowledged) return;
      }
      throw new Error("fulfillment_recovery_backlog_remaining");
  }
}
function failureCode(error: unknown): string {
  const message = error instanceof Error ? error.message : "";
  return /^[A-Za-z0-9_.-]{1,100}$/.test(message) ? message : "exception_business_repair_failed";
}

/** Source observation precedes acknowledgement. A failed/partial scan never resolves anything. */
export async function syncStorefrontExceptions(container: MedusaContainer, fetcher: typeof fetch = fetch): Promise<void> {
  const locking = container.resolve<ILockingModule>(Modules.LOCKING);
  await locking.execute("storefront:exception-worker", async () => {
    let scan = await collectStorefrontExceptionSources(container, fetcher);
    await publish(scan, fetcher);
    const pending = commands(await opsRequest("exceptions/commands", fetcher));
    for (const command of pending) {
      let error: unknown;
      if (scan.observations.some((row) => row.kind === command.kind && row.correlation_id === command.correlation_id)) {
        try { await executeRepair(container, command, fetcher); } catch (failure) { error = failure; }
      }
      // Scan timestamp starts after the effect. If it cannot be published, leave
      // the command pending; no result can pretend a partial read is convergence.
      scan = await collectStorefrontExceptionSources(container, fetcher);
      await publish(scan, fetcher);
      const remains = scan.observations.some((row) => row.kind === command.kind && row.correlation_id === command.correlation_id);
      await opsRequest(`exceptions/commands/${encodeURIComponent(command.id)}/result`, fetcher, {
        outcome: remains || error ? "not_repaired" : "repaired",
        detail: error ? failureCode(error) : remains ? "source_condition_still_present" : "fresh_complete_scan_confirms_source_convergence",
      });
    }
  }, { timeout: 5, expire: 600 });
}
