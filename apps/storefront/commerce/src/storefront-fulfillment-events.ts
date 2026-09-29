import { createHash } from "node:crypto";
import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import { withStorefrontOrderHandoffLock } from "./storefront-order-handoff";
import { enqueueFulfillmentStatusNotification } from "./storefront-notifications";

type JsonRecord = Record<string, any>;
export type FulfillmentStatus =
  | "ready_for_delivery"
  | "out_for_delivery"
  | "delivered"
  | "ready_for_collection"
  | "collected";
export type FulfillmentType = "delivery" | "collection";
export type StorefrontFulfillmentEvent = {
  event_id: string;
  company_id: string;
  external_order_id: string;
  revision: number;
  fulfillment_type: FulfillmentType;
  status: FulfillmentStatus;
  fulfillment_promise: Record<string, unknown> | null;
  occurred_at: string;
};

type AppliedState = {
  fulfillment_type: FulfillmentType;
  status: FulfillmentStatus;
  revision: number;
  event_id: string;
  updated_at: string;
  fulfillment_promise: Record<string, unknown> | null;
};
type EventDigest = { event_id: string; digest: string };

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" ? value as JsonRecord : {};
}

function safeFailureCode(error: unknown): string {
  const message = error instanceof Error ? error.message : "";
  return /^[A-Za-z0-9_-]{1,80}$/.test(message) ? message.toLowerCase() : "fulfillment_event_failed";
}

function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (!value || typeof value !== "object") return JSON.stringify(value);
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable((value as JsonRecord)[key])}`).join(",")}}`;
}

function samePromise(left: Record<string, unknown>, right: Record<string, unknown>): boolean {
  const leftAcceptedAt = Date.parse(String(left.accepted_at));
  const rightAcceptedAt = Date.parse(String(right.accepted_at));
  return Number.isFinite(leftAcceptedAt) && leftAcceptedAt === rightAcceptedAt &&
    stable({ ...left, accepted_at: leftAcceptedAt }) ===
    stable({ ...right, accepted_at: rightAcceptedAt });
}

function rank(type: FulfillmentType, status: string): number {
  const values = type === "delivery"
    ? ["confirmed", "ready_for_delivery", "out_for_delivery", "delivered"]
    : ["confirmed", "ready_for_collection", "collected"];
  return values.indexOf(status);
}

function validateEvent(event: StorefrontFulfillmentEvent): void {
  if (!/^[0-9a-f-]{36}$/i.test(event.event_id)) throw new Error("invalid_fulfillment_event_id");
  if (!event.external_order_id || !Number.isSafeInteger(event.revision) || event.revision <= 0) {
    throw new Error("invalid_fulfillment_event");
  }
  if (rank(event.fulfillment_type, event.status) < 1) throw new Error("invalid_fulfillment_status");
}

export function mergeFulfillmentEvent(
  current: AppliedState | null,
  processed: EventDigest[],
  event: StorefrontFulfillmentEvent,
  expectedPromise: Record<string, unknown> | null,
): { state: AppliedState; processed: EventDigest[]; changed: boolean; duplicate: boolean } {
  validateEvent(event);
  if (event.fulfillment_promise && expectedPromise && !samePromise(event.fulfillment_promise, expectedPromise)) {
    throw new Error("fulfillment_promise_mismatch");
  }

  const digest = createHash("sha256").update(stable(event)).digest("hex");
  const priorEvent = processed.find((item) => item.event_id === event.event_id);
  if (priorEvent && priorEvent.digest !== digest) throw new Error("fulfillment_event_id_conflict");
  if (priorEvent) return { state: current as AppliedState, processed, changed: false, duplicate: true };

  const history = [...processed, { event_id: event.event_id, digest }].slice(-256);
  const currentState = current || {
    fulfillment_type: event.fulfillment_type,
    status: "confirmed" as FulfillmentStatus,
    revision: 0,
    event_id: "",
    updated_at: event.occurred_at,
    fulfillment_promise: expectedPromise,
  };
  if (currentState.fulfillment_type !== event.fulfillment_type) {
    throw new Error("fulfillment_type_mismatch");
  }

  const isNewer = event.revision > currentState.revision;
  const movesForward = rank(event.fulfillment_type, event.status) > rank(event.fulfillment_type, currentState.status);
  const changed = isNewer && movesForward;
  const state = changed ? {
    fulfillment_type: event.fulfillment_type,
    status: event.status,
    revision: event.revision,
    event_id: event.event_id,
    updated_at: event.occurred_at,
    fulfillment_promise: expectedPromise || event.fulfillment_promise,
  } : currentState;
  return { state, processed: history, changed, duplicate: false };
}

async function getOrder(container: MedusaContainer, orderId: string): Promise<JsonRecord | undefined> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "order",
    fields: ["id", "display_id", "email", "metadata"],
    filters: { id: orderId },
  });
  return data[0] as JsonRecord | undefined;
}

export async function applyStorefrontFulfillmentEvent(
  container: MedusaContainer,
  event: StorefrontFulfillmentEvent,
): Promise<"applied" | "ignored" | "duplicate"> {
  validateEvent(event);
  const expectedCompany = process.env.FIRSTOUT_OPS_COMPANY_ID;
  if (!expectedCompany || event.company_id !== expectedCompany) throw new Error("fulfillment_company_mismatch");

  return withStorefrontOrderHandoffLock(container, event.external_order_id, async () => {
    const order = await getOrder(container, event.external_order_id);
    if (!order) throw new Error("storefront_order_not_found");
    const metadata = record(order.metadata);
    if (typeof metadata.storefront_confirmation_sha256 !== "string") {
      throw new Error("storefront_order_capability_missing");
    }
    const expectedPromise = record(metadata).storefront_fulfillment_promise || null;
    const currentValue = metadata.storefront_fulfillment_status;
    const current = currentValue && typeof currentValue === "object"
      ? currentValue as AppliedState
      : null;
    const processed = Array.isArray(metadata.storefront_fulfillment_events)
      ? metadata.storefront_fulfillment_events as EventDigest[]
      : [];
    const merged = mergeFulfillmentEvent(current, processed, event, expectedPromise);
    if (merged.duplicate) return "duplicate";

    const nextMetadata: JsonRecord = {
      ...metadata,
      storefront_fulfillment_status: merged.state,
      storefront_fulfillment_events: merged.processed,
    };
    if (merged.changed) {
      nextMetadata.storefront_notification_outbox = enqueueFulfillmentStatusNotification(
        metadata.storefront_notification_outbox,
        { ...metadata, display_id: order.display_id, email: order.email },
        event,
      );
    }
    const orderModule = container.resolve(Modules.ORDER);
    await orderModule.updateOrders([{ id: order.id, metadata: nextMetadata }]);
    order.metadata = nextMetadata;
    return merged.changed ? "applied" : "ignored";
  });
}

function requiredConfig(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`storefront_${name.toLowerCase()}_unconfigured`);
  return value;
}

function endpoint(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export async function syncStorefrontFulfillmentEvents(
  container: MedusaContainer,
  fetcher: typeof fetch = fetch,
): Promise<{ received: number; acknowledged: number }> {
  const base = requiredConfig("FIRSTOUT_OPS_URL");
  const token = requiredConfig("FIRSTOUT_OPS_TOKEN");
  const companyId = requiredConfig("FIRSTOUT_OPS_COMPANY_ID");
  const headers = {
    authorization: `Bearer ${token}`,
    "x-ops-company-id": companyId,
    "content-type": "application/json",
  };
  const feed = await fetcher(endpoint(base, "fulfillment-events?limit=100"), {
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!feed.ok) throw new Error(`fulfillment_feed_http_${feed.status}`);
  const body = await feed.json() as { items?: StorefrontFulfillmentEvent[] };
  const events = Array.isArray(body.items) ? body.items : [];
  const accepted: string[] = [];
  for (const event of events) {
    try {
      await applyStorefrontFulfillmentEvent(container, event);
      accepted.push(event.event_id);
    } catch (error) {
      // Keep the event in Firstout until this Medusa instance can durably apply it.
      console.warn("Storefront fulfilment event remains pending", {
        event_id: event?.event_id,
        failure: safeFailureCode(error),
      });
    }
  }
  if (!accepted.length) return { received: events.length, acknowledged: 0 };
  const ack = await fetcher(endpoint(base, "fulfillment-events/ack"), {
    method: "POST",
    headers,
    body: JSON.stringify({ event_ids: accepted }),
    signal: AbortSignal.timeout(10000),
  });
  if (!ack.ok) throw new Error(`fulfillment_ack_http_${ack.status}`);
  const ackBody = await ack.json() as { acknowledged?: number };
  return { received: events.length, acknowledged: ackBody.acknowledged || 0 };
}
