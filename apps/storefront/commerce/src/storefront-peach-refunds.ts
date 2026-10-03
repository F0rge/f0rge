import { randomUUID } from "node:crypto";
import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import { createOrderCreditLinesWorkflow } from "@medusajs/core-flows";
import type { Knex } from "knex";
import { medusaAmountToMinor, minorToMajor, type PeachWebhookEvent } from "./peach-checkout";
import { peachPaymentConfig, peachRefundEnabled } from "./peach-payment-config";
import { peachRefundOutcome, peachRefundPayment, type PeachRefundObservation } from "./peach-refunds";
import { enqueueRefundStatusNotification } from "./storefront-notifications";
import { withStorefrontOrderHandoffLock } from "./storefront-order-handoff";
import {
  claimPeachRefundForMedusa, claimPeachRefundDispatchForDispatch, createPeachRefundDispatch, findPeachAttemptByCapturedTransactionId,
  findPeachRefundByProviderId, findPeachRefundDispatch, markPeachRefundDispatchUnknownIfUnresolved,
  PEACH_REFUNDS_TABLE, type PeachInboxEvent, type PeachRefundCommand, type PeachRefundDispatch,
  updatePeachRefundDispatch, receivePeachWebhook, claimPeachWebhook, completePeachWebhook, retryPeachWebhook,
} from "./peach-payment-store";

type JsonRecord = Record<string, any>;
type ResolutionStatus = "succeeded" | "pending" | "failed" | "needs_review";
type ProviderOutcome = "succeeded" | "pending" | "failed" | "unknown";
type RefundResolution = {
  status: ResolutionStatus;
  provider_outcome: ProviderOutcome;
  resolution_code?: string | null;
  request_id?: string | null;
  external_order_id?: string | null;
  handoff_id?: string | null;
  amount_minor: number;
  currency_code: string;
  provider_refund_id: string;
};

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function requiredConfig(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`storefront_${name.toLowerCase()}_unconfigured`);
  return value;
}

function opsBase(): string {
  return requiredConfig("FIRSTOUT_OPS_URL").replace(/\/+$/, "");
}

function opsHeaders(): Record<string, string> {
  return {
    authorization: `Bearer ${requiredConfig("FIRSTOUT_OPS_TOKEN")}`,
    "x-ops-company-id": requiredConfig("FIRSTOUT_OPS_COMPANY_ID"),
    "content-type": "application/json",
  };
}

function endpoint(path: string): string {
  return `${opsBase()}/${path.replace(/^\/+/, "")}`;
}

function safeCode(value: unknown): string {
  return typeof value === "string" && /^[A-Za-z0-9_.-]{1,80}$/.test(value) ? value : "refund_processing_failed";
}

function validCommand(value: unknown): value is PeachRefundCommand {
  const item = record(value);
  return typeof item.request_id === "string" && item.request_id.length > 0 &&
    typeof item.handoff_id === "string" && item.handoff_id.length > 0 &&
    typeof item.external_order_id === "string" && item.external_order_id.length > 0 &&
    typeof item.original_transaction_id === "string" && /^[a-f0-9]{32}$/i.test(item.original_transaction_id) &&
    Number.isSafeInteger(item.amount_minor) && item.amount_minor > 0 &&
    item.currency_code === "ZAR" && typeof item.cancel_order === "boolean" && typeof item.status === "string";
}

async function postCommandOutcome(
  commandId: string,
  status: "dispatching" | "unknown" | "pending",
  fetcher: typeof fetch,
  failureCode?: string,
  dispatchCommand?: PeachRefundCommand,
): Promise<boolean> {
  const response = await fetcher(endpoint(`refund-commands/${encodeURIComponent(commandId)}/outcome`), {
    method: "POST",
    headers: opsHeaders(),
    body: JSON.stringify({ status, ...(failureCode ? { failure_code: failureCode } : {}) }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) return false;
  if (status !== "dispatching") return true;
  if (!dispatchCommand) return false;
  return confirmsRefundDispatchingResponse(response, dispatchCommand);
}

/** A 2xx alone is not permission to contact Peach: Firstout may return an
 * unchanged terminal refund. Confirm the exact immutable intent transitioned
 * to dispatching before making the external money-moving request. */
export function confirmsRefundDispatchingBarrier(value: unknown, command: PeachRefundCommand): boolean {
  const body = record(value);
  return body.id === command.request_id && body.status === "dispatching" &&
    body.amount_minor === command.amount_minor && body.currency_code === command.currency_code;
}

export async function confirmsRefundDispatchingResponse(
  response: Response,
  command: PeachRefundCommand,
): Promise<boolean> {
  if (!response.ok) return false;
  try { return confirmsRefundDispatchingBarrier(await response.json(), command); }
  catch { return false; }
}

function eventFromObservation(
  observation: PeachRefundObservation,
  requestId: string | null,
  webhookId: string | null,
): PeachWebhookEvent {
  return {
    webhook_id: webhookId,
    checkout_id: "",
    merchant_reference: "",
    amount_minor: observation.amount_minor,
    currency_code: observation.currency_code,
    payment_type: "RF",
    result_code: observation.result_code,
    transaction_id: observation.provider_refund_id,
    referenced_transaction_id: observation.referenced_capture_id,
    refund_request_id: requestId,
    event_timestamp: observation.event_timestamp,
    raw_sha256: observation.canonical_sha256,
    canonical_sha256: observation.canonical_sha256,
  };
}

async function sendRefundEventToFirstout(
  event: PeachWebhookEvent,
  eventSource: "webhook" | "response",
  fetcher: typeof fetch,
): Promise<RefundResolution> {
  const amountMinor = Number(event.amount_minor);
  if (!Number.isSafeInteger(amountMinor) || amountMinor <= 0) throw new Error("refund_event_amount_invalid");
  const response = await fetcher(endpoint("refund-events"), {
    method: "POST",
    headers: opsHeaders(),
    body: JSON.stringify({
      ...(event.refund_request_id ? { request_id: event.refund_request_id } : {}),
      provider_refund_id: event.transaction_id,
      ...(event.webhook_id ? { webhook_id: event.webhook_id } : {}),
      event_source: eventSource,
      referenced_capture_id: event.referenced_transaction_id,
      amount_minor: amountMinor,
      currency_code: event.currency_code,
      result_code: event.result_code,
      outcome: peachRefundOutcome(event.result_code),
      event_timestamp: event.event_timestamp,
      canonical_sha256: event.canonical_sha256,
      signature_verified: true,
    }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new Error(`refund_event_http_${response.status}`);
  const body = record(await response.json());
  const status = body.status;
  if (!["succeeded", "pending", "failed", "needs_review"].includes(status)) {
    throw new Error("refund_event_response_invalid");
  }
  if (body.resolution_code !== undefined && body.resolution_code !== null &&
    (typeof body.resolution_code !== "string" || !/^[A-Za-z0-9_.-]{1,80}$/.test(body.resolution_code))) {
    throw new Error("refund_event_resolution_code_invalid");
  }
  const resolution = body as RefundResolution;
  if (!["succeeded", "pending", "failed", "unknown"].includes(resolution.provider_outcome) ||
    (status !== "needs_review" && (typeof resolution.request_id !== "string" || !resolution.request_id ||
    typeof resolution.external_order_id !== "string" || !resolution.external_order_id)) ||
    !Number.isSafeInteger(resolution.amount_minor) || resolution.amount_minor !== amountMinor ||
    resolution.currency_code !== event.currency_code || resolution.provider_refund_id !== event.transaction_id) {
    throw new Error("refund_event_resolution_mismatch");
  }
  return resolution;
}

async function markUnknown(
  db: Knex,
  requestId: string,
  fetcher: typeof fetch,
  failureCode: string,
): Promise<void> {
  if (!await markPeachRefundDispatchUnknownIfUnresolved(db, requestId)) return;
  try { await postCommandOutcome(requestId, "unknown", fetcher, safeCode(failureCode)); }
  catch { /* The local unknown state prevents a blind provider resend. */ }
}

/**
 * Pulls authorized commands from Firstout. Peach credentials are fetched before
 * setting dispatching; after dispatching is durable, every ambiguous result is
 * recorded unknown and the provider POST is never automatically repeated.
 */
export async function syncStorefrontPeachRefundCommands(
  container: MedusaContainer,
  fetcher: typeof fetch = fetch,
): Promise<{ received: number; dispatched: number }> {
  const config = peachPaymentConfig();
  if (!config) return { received: 0, dispatched: 0 };
  const db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  let commands: unknown[] = [];
  let dispatched = 0;
  // Removing the signing secret disables new provider requests, but verified
  // money already returned must still converge into Medusa and customer state.
  if (peachRefundEnabled()) {
    try {
      const feed = await fetcher(endpoint("refund-commands?limit=100"), {
        headers: opsHeaders(), cache: "no-store", signal: AbortSignal.timeout(10_000),
      });
      if (!feed.ok) throw new Error(`refund_command_feed_http_${feed.status}`);
      const body = record(await feed.json());
      commands = Array.isArray(body.items) ? body.items : [];
      for (const item of commands) {
        if (!validCommand(item) || !["requested", "dispatching"].includes(item.status)) continue;
        try {
          await processRefundCommand(container, db, config, item, fetcher);
          dispatched += 1;
        } catch (error) {
          console.warn("Storefront Peach refund command remains pending", {
            request_id: item.request_id,
            failure: safeCode(error instanceof Error ? error.message : ""),
          });
        }
      }
    } catch (error) {
      // A remote queue outage must not block local convergence of already
      // verified money or the independently durable Peach inbox.
      console.warn("Storefront Peach refund command feed unavailable", {
        failure: safeCode(error instanceof Error ? error.message : ""),
      });
    }
  }
  await reconcileVerifiedMedusaRefunds(container, db);
  return { received: commands.length, dispatched };
}

async function processRefundCommand(
  container: MedusaContainer,
  db: Knex,
  config: NonNullable<ReturnType<typeof peachPaymentConfig>>,
  command: PeachRefundCommand,
  fetcher: typeof fetch,
): Promise<void> {
  await withRefundLock(container, command.request_id, async () => {
    const { dispatch } = await createPeachRefundDispatch(db, command);
    // A remote dispatching status means a previous worker crossed Firstout's
    // durable barrier. Its provider POST may have happened even if no response
    // was persisted, so recovery can only mark unknown; it must never resend.
    if (command.status === "dispatching" || dispatch.status === "dispatching") {
      if (!["received", "dispatching", "unknown"].includes(dispatch.status)) return;
      await markUnknown(db, command.request_id, fetcher, "recovered_dispatch_without_result");
      return;
    }
    if (dispatch.status !== "received") return;

    // Checkout V1 refund authorization uses its dedicated HMAC signing secret;
    // the OAuth token belongs to the separate Hosted Checkout V2 API.
    if (!await claimPeachRefundDispatchForDispatch(db, command.request_id)) return;
    let outcomeSent = false;
    try { outcomeSent = await postCommandOutcome(command.request_id, "dispatching", fetcher, undefined, command); }
    catch { /* No refund POST unless Firstout durably accepts dispatching. */ }
    if (!outcomeSent) {
      await markUnknown(db, command.request_id, fetcher, "dispatch_state_unconfirmed");
      return;
    }

    let observation: PeachRefundObservation | null;
    try {
      observation = await peachRefundPayment(config, {
        referencedCaptureId: command.original_transaction_id,
        amountMinor: command.amount_minor,
        currencyCode: command.currency_code,
      }, fetcher);
    } catch (error) {
      await markUnknown(db, command.request_id, fetcher, safeCode(error instanceof Error ? error.message : ""));
      return;
    }
    if (!observation) {
      await markUnknown(db, command.request_id, fetcher, "refund_response_unverified");
      return;
    }

    const event = eventFromObservation(observation, command.request_id, null);
    const persisted = await receivePeachWebhook(db, event, null, "refund-response");
    const claimed = await claimPeachWebhook(db, persisted.id);
    if (!claimed) return;
    let result: "processed" | "needs_review" | "pending";
    try {
      result = await processClaimedPeachRefundWebhook(container, db, claimed, fetcher);
    } catch (error) {
      await retryPeachWebhook(db, claimed.id, claimed.lease_token, safeCode(error instanceof Error ? error.message : ""));
      throw error;
    }
    await completePeachWebhook(db, claimed.id, claimed.lease_token, result === "needs_review" ? "needs_review" : "processed");
    if (result === "pending") {
      await postCommandOutcome(command.request_id, "pending", fetcher);
    }
  });
}

export async function processClaimedPeachRefundWebhook(
  container: MedusaContainer,
  db: Knex,
  event: PeachInboxEvent,
  fetcher: typeof fetch = fetch,
): Promise<"processed" | "needs_review" | "pending"> {
  if (event.payment_type !== "RF" || !event.referenced_transaction_id || !event.transaction_id) {
    throw new Error("peach_refund_event_invalid");
  }
  const observation: PeachRefundObservation = {
    provider_refund_id: event.transaction_id,
    referenced_capture_id: event.referenced_transaction_id,
    amount_minor: Number(event.amount_minor),
    currency_code: event.currency_code,
    result_code: event.result_code,
    outcome: peachRefundOutcome(event.result_code),
    event_timestamp: event.event_timestamp,
    canonical_sha256: event.canonical_sha256,
  };
  const normalizedEvent = eventFromObservation(observation, event.refund_request_id, event.webhook_id);
  return persistAndProcessRefundObservation(container, db, normalizedEvent,
    event.source === "refund-response" ? "refund-response" : "webhook", fetcher);
}

export async function persistAndProcessRefundObservation(
  container: MedusaContainer,
  db: Knex,
  event: PeachWebhookEvent,
  source: "webhook" | "refund-response",
  fetcher: typeof fetch,
): Promise<"processed" | "needs_review" | "pending"> {
  const localByProviderId = await findPeachRefundByProviderId(db, event.transaction_id || "");
  let localByRequest = event.refund_request_id
    ? await findPeachRefundDispatch(db, event.refund_request_id)
    : undefined;
  // A matching capture and amount do not prove the event belongs to our
  // request. Staff can create refunds in Peach independently while an
  // equally-sized local intent remains unresolved, so never guess here.
  const localIdentityConflict = Boolean(
    localByProviderId && localByRequest && localByProviderId.request_id !== localByRequest.request_id,
  );
  const known = localByProviderId || localByRequest;
  const knownConflict = Boolean(known && (known.original_transaction_id.toLowerCase() !== event.referenced_transaction_id?.toLowerCase() ||
    Number(known.amount_minor) !== Number(event.amount_minor) || known.currency_code !== event.currency_code ||
    (known.provider_refund_id && known.provider_refund_id !== event.transaction_id)));
  const resolution = await sendRefundEventToFirstout(event, source === "webhook" ? "webhook" : "response", fetcher);
  // Firstout records this immutable signed event separately. Never copy its
  // conflicting provider ID, amount, status, or digest onto a different local
  // dispatch, even when the previous dispatch already consumed the capability
  // and created a native Medusa refund. The durable inbox row is the review
  // observation for this event.
  if (localIdentityConflict || knownConflict || resolution.resolution_code) {
    return "needs_review";
  }

  if (!resolution.request_id || !resolution.external_order_id) {
    // An ambiguous out-of-band event is durably recorded by Firstout, but has
    // no safe Medusa order or refund association yet.
    return "needs_review";
  }
  const command: PeachRefundCommand = {
    request_id: resolution.request_id,
    handoff_id: resolution.handoff_id || known?.handoff_id || "external",
    external_order_id: resolution.external_order_id,
    original_transaction_id: event.referenced_transaction_id || "",
    amount_minor: Number(event.amount_minor),
    currency_code: event.currency_code,
    cancel_order: known?.cancel_order || false,
    allocation: known?.allocation || {},
    status: "resolved",
  };
  const { dispatch } = await createPeachRefundDispatch(db, command);
  const successfulDispatchIsAlreadyFinal = dispatch.status === "succeeded" && resolution.provider_outcome === "succeeded";
  await updatePeachRefundDispatch(db, dispatch.request_id, {
    ...(!successfulDispatchIsAlreadyFinal ? {
      status: resolution.provider_outcome === "succeeded" ? "verified" : resolution.provider_outcome === "unknown"
        ? "needs_review" : resolution.provider_outcome,
    } : {}),
    firstout_status: resolution.status,
    provider_refund_id: event.transaction_id,
    provider_result_code: event.result_code,
    canonical_sha256: event.canonical_sha256,
  });
  if (successfulDispatchIsAlreadyFinal) return "processed";
  if (resolution.provider_outcome !== "succeeded") {
    if (resolution.provider_outcome === "pending" || resolution.provider_outcome === "failed") {
      await recordCustomerRefundStatus(container, resolution.external_order_id, event, resolution.provider_outcome);
    }
    return resolution.provider_outcome === "pending" ? "pending" : "processed";
  }

  const orderId = resolution.external_order_id || (event.referenced_transaction_id
    ? (await findPeachAttemptByCapturedTransactionId(db, event.referenced_transaction_id))?.captured_order_id || ""
    : "");
  const paymentId = await findMedusaPaymentForRefund(container, orderId, event.referenced_transaction_id || "");
  if (!paymentId) {
    await updatePeachRefundDispatch(db, dispatch.request_id, { status: "needs_review" });
    return "needs_review";
  }
  await updatePeachRefundDispatch(db, dispatch.request_id, { status: "verified", medusa_payment_id: paymentId });
  const applied = await ensureNativeMedusaRefund(container, db, dispatch.request_id, paymentId);
  if (!applied) return "needs_review";
  await recordCustomerRefundStatus(container, orderId, event, "succeeded");
  await updatePeachRefundDispatch(db, dispatch.request_id, { status: "succeeded" });
  return "processed";
}

export function customerRefundStatusProjection(
  metadataValue: unknown,
  order: { email: unknown; display_id: unknown },
  event: PeachWebhookEvent,
  status: "pending" | "succeeded" | "failed",
): JsonRecord | null {
  const providerRefundId = event.transaction_id;
  const amountMinor = Number(event.amount_minor);
  if (!providerRefundId || !Number.isSafeInteger(amountMinor) || amountMinor <= 0) return null;
  const metadata = record(metadataValue);
  const refunds: JsonRecord[] = Array.isArray(metadata.storefront_refunds)
    ? metadata.storefront_refunds.map(record) : [];
  const existingIndex = refunds.findIndex((refund) => refund.provider_refund_id === providerRefundId);
  const existing = existingIndex >= 0 ? refunds[existingIndex] : undefined;
  if (existing && (Number(existing.amount_minor) !== amountMinor || existing.currency_code !== event.currency_code)) {
    throw new Error("storefront_refund_identity_conflict");
  }
  // Provider reconciliation is monotonic: an earlier terminal decline can be
  // corrected by a later verified success, while a stale pending/failed
  // callback can never downgrade money already confirmed returned.
  if (existing?.status === "succeeded" || existing?.status === status ||
    (existing?.status === "failed" && status !== "succeeded")) return null;
  const item = {
    provider_refund_id: providerRefundId,
    amount_minor: amountMinor,
    currency_code: event.currency_code,
    status,
  };
  const nextRefunds = existingIndex < 0 ? [...refunds, item]
    : refunds.map((refund, index) => index === existingIndex ? item : refund);
  const outbox = enqueueRefundStatusNotification(metadata.storefront_notification_outbox, {
    ...metadata, email: order.email, display_id: order.display_id,
  }, item);
  return { ...metadata, storefront_refunds: nextRefunds, storefront_notification_outbox: outbox };
}

export async function recordCustomerRefundStatus(
  container: MedusaContainer,
  orderId: string,
  event: PeachWebhookEvent,
  status: "pending" | "succeeded" | "failed",
): Promise<void> {
  const providerRefundId = event.transaction_id;
  if (!orderId || !providerRefundId || !Number.isSafeInteger(event.amount_minor)) return;
  await withStorefrontOrderHandoffLock(container, orderId, async () => {
    const query = container.resolve(ContainerRegistrationKeys.QUERY);
    const { data } = await query.graph({
      entity: "order", fields: ["id", "display_id", "email", "metadata"], filters: { id: orderId },
    });
    const order = record(data[0]);
    if (typeof order.id !== "string") throw new Error("storefront_refund_order_not_found");
    const nextMetadata = customerRefundStatusProjection(order.metadata, {
      email: order.email, display_id: order.display_id,
    }, event, status);
    if (!nextMetadata) return;
    const orderModule = container.resolve(Modules.ORDER);
    await orderModule.updateOrders([{
      id: order.id, metadata: nextMetadata,
    }]);
  });
}

async function findMedusaPaymentForRefund(
  container: MedusaContainer,
  orderId: string,
  captureId: string,
): Promise<string | null> {
  if (!orderId) return null;
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "order",
    fields: ["id", "payment_collections.payments.id", "payment_collections.payments.provider_id", "payment_collections.payments.data", "payment_collections.payments.amount", "payment_collections.payments.currency_code"],
    filters: { id: orderId },
  });
  const order = record(data[0]);
  const collections: JsonRecord[] = Array.isArray(order.payment_collections) ? order.payment_collections.map(record) : [];
  const payments = collections.flatMap((collection) => Array.isArray(collection.payments) ? collection.payments.map(record) : []);
  const match = payments.find((payment) => payment.provider_id === "pp_peach_sandbox" &&
    record(payment.data).transaction_id === captureId && typeof payment.id === "string");
  return typeof match?.id === "string" ? match.id : null;
}

async function existingRefundRow(db: Knex, refundId: string): Promise<JsonRecord | undefined> {
  return db("refund").where({ id: refundId }).whereNull("deleted_at").first();
}

async function ensureNativeMedusaRefund(
  container: MedusaContainer,
  db: Knex,
  requestId: string,
  paymentId: string,
): Promise<boolean> {
  const dispatch = await findPeachRefundDispatch(db, requestId);
  if (!dispatch || !dispatch.provider_refund_id || Number(dispatch.amount_minor) <= 0) return false;
  // Every refund on one order changes the same native Order summary. Serialize
  // those local convergence steps while allowing unrelated orders to proceed.
  return withRefundLock(container, `medusa-order:${dispatch.external_order_id}`, async () => {
    const fresh = await findPeachRefundDispatch(db, requestId);
    if (!fresh || !fresh.provider_refund_id) return false;
    if (fresh.medusa_refund_id) {
      const row = await existingRefundRow(db, fresh.medusa_refund_id);
      if (row) {
        try {
          await ensureNativeOrderRefundAccounting(
            container, orderIdFromDispatch(fresh), fresh.medusa_refund_id,
            Number(fresh.amount_minor), fresh.currency_code,
          );
        } catch {
          // The gateway outcome is already verified. Leave the local dispatch
          // replayable until Order's transaction and credit line converge.
          return false;
        }
        await db("refund").where({ id: fresh.medusa_refund_id }).update({
          metadata: { storefront_peach_refund: { request_id: requestId, provider_refund_id: fresh.provider_refund_id } },
          updated_at: new Date(),
        });
        return true;
      }
      // A failed Medusa bookkeeping transaction may have removed the draft
      // Refund after the provider gate claimed it. Peach already succeeded, so
      // only retry the local record creation; never repeat the gateway POST.
      await updatePeachRefundDispatch(db, requestId, {
        status: "verified", medusa_refund_id: null, authorization_key: null,
      });
    }

    const capability = randomUUID();
    await updatePeachRefundDispatch(db, requestId, {
      status: "verified", authorization_key: capability, medusa_payment_id: paymentId,
    });
    const paymentModule = container.resolve(Modules.PAYMENT) as unknown as {
      refundPayment(input: Record<string, unknown>): Promise<JsonRecord>;
    };
    try {
      await paymentModule.refundPayment({
        payment_id: paymentId,
        amount: minorToMajor(Number(fresh.amount_minor)),
        created_by: "storefront-refund-reconciler",
        note: `Peach refund ${fresh.provider_refund_id}`,
        metadata: {
          storefront_peach_refund: {
            request_id: requestId,
            provider_refund_id: fresh.provider_refund_id,
            authorization_key: capability,
          },
        },
      });
    } catch {
      const after = await findPeachRefundDispatch(db, requestId);
      if (after?.medusa_refund_id) {
        const row = await existingRefundRow(db, after.medusa_refund_id);
        if (row) {
          try {
            await ensureNativeOrderRefundAccounting(
              container, orderIdFromDispatch(after), after.medusa_refund_id,
              Number(after.amount_minor), after.currency_code,
            );
          } catch {
            return false;
          }
          await db("refund").where({ id: after.medusa_refund_id }).update({
            metadata: { storefront_peach_refund: { request_id: requestId, provider_refund_id: fresh.provider_refund_id } },
            updated_at: new Date(),
          });
          return true;
        }
        await updatePeachRefundDispatch(db, requestId, {
          status: "verified", medusa_refund_id: null, authorization_key: null,
        });
      }
      return false;
    }
    const after = await findPeachRefundDispatch(db, requestId);
    if (!after?.medusa_refund_id) return false;
    const row = await existingRefundRow(db, after.medusa_refund_id);
    if (!row) {
      await updatePeachRefundDispatch(db, requestId, {
        status: "verified", medusa_refund_id: null, authorization_key: null,
      });
      return false;
    }
    try {
      await ensureNativeOrderRefundAccounting(
        container, orderIdFromDispatch(after), after.medusa_refund_id,
        Number(after.amount_minor), after.currency_code,
      );
    } catch {
      return false;
    }
    await db("refund").where({ id: after.medusa_refund_id }).update({
      metadata: { storefront_peach_refund: { request_id: requestId, provider_refund_id: after.provider_refund_id } },
      updated_at: new Date(),
    });
    return true;
  });
}

function orderIdFromDispatch(dispatch: PeachRefundDispatch): string {
  return dispatch.external_order_id;
}

async function ensureNativeOrderRefundAccounting(
  container: MedusaContainer,
  orderId: string,
  refundId: string,
  amountMinor: number,
  currencyCode: string,
): Promise<void> {
  const orderModule = container.resolve(Modules.ORDER) as unknown as {
    listOrderTransactions(filters: JsonRecord, config: JsonRecord): Promise<JsonRecord[]>;
    addOrderTransactions(transactions: JsonRecord[]): Promise<JsonRecord[]>;
    confirmOrderChange(changes: string[]): Promise<unknown>;
  };
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const transactionRows = await orderModule.listOrderTransactions({
    order_id: orderId, reference: "refund", reference_id: refundId,
  }, { select: ["id", "order_id", "amount", "currency_code", "reference", "reference_id"] });
  const orderGraph = await query.graph({
    entity: "order", fields: ["id", "currency_code", "summary.pending_difference", "summary.raw_pending_difference"], filters: { id: orderId },
  });
  const order = record(orderGraph.data[0]);
  const summary = record(order.summary);
  const pendingDifferenceMinor = medusaAmountToMinor(summary.raw_pending_difference ?? summary.pending_difference);
  if (order.id !== orderId || pendingDifferenceMinor === null) {
    throw new Error("storefront_refund_order_summary_unavailable");
  }
  const beforeRefundDifference = transactionRows.length
    ? pendingDifferenceMinor - amountMinor
    : pendingDifferenceMinor;
  if (!transactionRows.length) {
    await orderModule.addOrderTransactions([{
      order_id: orderId,
      amount: -minorToMajor(amountMinor),
      currency_code: currencyCode,
      reference: "refund",
      reference_id: refundId,
    }]);
  } else if (Number(transactionRows[0].amount) !== -minorToMajor(amountMinor) ||
    String(transactionRows[0].currency_code).toUpperCase() !== currencyCode.toUpperCase()) {
    throw new Error("storefront_refund_order_transaction_conflict");
  }

  const creditLineMinor = beforeRefundDifference < 0
    ? Math.max(0, amountMinor + beforeRefundDifference)
    : amountMinor;
  if (!creditLineMinor) return;
  const changes = await query.graph({
    entity: "order_change",
    fields: ["id", "status", "actions.id", "actions.action", "actions.reference", "actions.reference_id"],
    filters: { order_id: orderId },
  });
  const matchingChange = (changes.data as JsonRecord[]).find((change) =>
    Array.isArray(change.actions) && change.actions.some((actionValue: unknown) => {
      const action = record(actionValue);
      return action.action === "CREDIT_LINE_ADD" && action.reference === "storefront_refund" &&
        action.reference_id === refundId;
    }));
  if (matchingChange) {
    if (matchingChange.status === "confirmed") return;
    if (matchingChange.status === "pending" && typeof matchingChange.id === "string") {
      await orderModule.confirmOrderChange([matchingChange.id]);
      return;
    }
    throw new Error("storefront_refund_credit_line_requires_review");
  }
  if ((changes.data as JsonRecord[]).some((change) => change.status === "pending")) {
    throw new Error("storefront_order_change_requires_review");
  }
  await createOrderCreditLinesWorkflow(container).run({
    input: {
      id: orderId,
      credit_lines: [{
        amount: minorToMajor(creditLineMinor),
        reference: "storefront_refund",
        reference_id: refundId,
      }],
    },
  });
}

async function reconcileVerifiedMedusaRefunds(container: MedusaContainer, db: Knex): Promise<void> {
  const rows = await db<PeachRefundDispatch>(PEACH_REFUNDS_TABLE).whereNull("deleted_at")
    .whereIn("status", ["verified", "recording_medusa_refund"]).limit(25);
  for (const row of rows) {
    if (!row.medusa_payment_id) continue;
    try {
      const applied = await ensureNativeMedusaRefund(container, db, row.request_id, row.medusa_payment_id);
      if (applied && row.provider_refund_id) {
        await recordCustomerRefundStatus(container, row.external_order_id, {
          transaction_id: row.provider_refund_id,
          amount_minor: Number(row.amount_minor),
          currency_code: row.currency_code,
        } as PeachWebhookEvent, "succeeded");
        await updatePeachRefundDispatch(db, row.request_id, { status: "succeeded" });
      }
    }
    catch { /* A verified refund remains durable and is retried locally. */ }
  }
}

async function withRefundLock<T>(container: MedusaContainer, key: string, operation: () => Promise<T>): Promise<T> {
  const locking = container.resolve(Modules.LOCKING) as unknown as { execute<T>(key: string, operation: () => Promise<T>): Promise<T> };
  return locking.execute(`storefront:peach-refund:${key}`, operation);
}
