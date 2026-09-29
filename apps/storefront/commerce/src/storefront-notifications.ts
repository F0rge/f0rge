import { createHmac } from "node:crypto";
import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import { withStorefrontOrderHandoffLock } from "./storefront-order-handoff";

type JsonRecord = Record<string, any>;
type NotificationStatus = "pending" | "processing" | "retry_wait" | "sent";
type NotificationEntry = {
  id: string;
  kind: "order_confirmation" | "fulfillment_status";
  status: NotificationStatus;
  recipient: string;
  template: string;
  data: JsonRecord;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  next_attempt_at: string | null;
  lease_until: string | null;
  sent_at: string | null;
  failure_code: string | null;
};

const OUTBOX_KEY = "storefront_notification_outbox";
const ORDER_FIELDS = [
  "id", "display_id", "email", "currency_code", "created_at", "metadata",
  "items.id", "items.title", "items.quantity", "items.unit_price", "items.total", "items.metadata",
];

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function entries(value: unknown): NotificationEntry[] {
  return Array.isArray(value) ? value.filter((entry) => entry && typeof entry.id === "string") as NotificationEntry[] : [];
}

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name.toLowerCase()}_unconfigured`);
  return value;
}

function providerTemplate(entry: NotificationEntry): string {
  const template = entry.kind === "order_confirmation"
    ? process.env.STOREFRONT_SENDGRID_ORDER_TEMPLATE_ID
    : process.env.STOREFRONT_SENDGRID_STATUS_TEMPLATE_ID;
  if (process.env.STOREFRONT_SENDGRID_API_KEY && !template?.trim()) {
    throw new Error(`sendgrid_${entry.kind}_template_unconfigured`);
  }
  return template?.trim() || entry.template;
}

function accessUrl(orderId: string, confirmationDigest: string): string {
  const secret = required("STOREFRONT_BFF_SECRET");
  if (secret.length < 32 || !/^[a-f0-9]{64}$/i.test(confirmationDigest)) {
    throw new Error("storefront_order_access_unconfigured");
  }
  const token = createHmac("sha256", secret)
    .update(`storefront-order-status:v1:${orderId}:${confirmationDigest}`)
    .digest("base64url");
  const base = required("STOREFRONT_PUBLIC_URL").replace(/\/+$/, "");
  return `${base}/order/confirmation#order_id=${encodeURIComponent(orderId)}&access=${token}`;
}

function orderSnapshot(order: JsonRecord): JsonRecord {
  const metadata = record(order.metadata);
  const promise = metadata.storefront_fulfillment_promise ?? null;
  return {
    reference: order.display_id,
    currency_code: order.currency_code,
    created_at: order.created_at,
    fulfillment_promise: promise,
    items: (Array.isArray(order.items) ? order.items : []).map((item: JsonRecord) => ({
      title: item.title,
      quantity: item.quantity,
      unit_price: item.unit_price,
      total: item.total,
      fulfillment_promise: record(item.metadata).fulfillment_promise ?? null,
    })),
  };
}

function confirmationEntry(order: JsonRecord, now: Date): NotificationEntry | null {
  const metadata = record(order.metadata);
  const digest = metadata.storefront_confirmation_sha256;
  const recipient = typeof order.email === "string" ? order.email.trim().toLowerCase() : "";
  if (!recipient || typeof digest !== "string") return null;
  return {
    id: `confirmation:${order.id}`,
    kind: "order_confirmation",
    status: "pending",
    recipient,
    template: "storefront-order-confirmation",
    data: { order: orderSnapshot(order) },
    attempt_count: 0,
    created_at: now.toISOString(),
    updated_at: now.toISOString(),
    next_attempt_at: now.toISOString(),
    lease_until: null,
    sent_at: null,
    failure_code: null,
  };
}

/** Pure queue operation used in the same Medusa metadata write as the status merge. */
export function enqueueFulfillmentStatusNotification(
  current: unknown,
  orderMetadata: JsonRecord,
  event: {
    event_id: string;
    external_order_id: string;
    status: string;
    fulfillment_type: string;
    revision: number;
    occurred_at: string;
    fulfillment_promise: Record<string, unknown> | null;
  },
): NotificationEntry[] {
  const outbox = entries(current);
  const id = `fulfillment:${event.event_id}`;
  if (outbox.some((entry) => entry.id === id)) return outbox;
  const recipient = typeof orderMetadata.email === "string" ? orderMetadata.email.trim().toLowerCase() : "";
  if (!recipient) throw new Error("storefront_order_email_missing");
  const now = new Date().toISOString();
  return [...outbox, {
    id,
    kind: "fulfillment_status",
    status: "pending",
    recipient,
    template: "storefront-fulfillment-status",
    data: {
      order: {
        reference: orderMetadata.display_id,
        fulfillment_promise: orderMetadata.storefront_fulfillment_promise ?? null,
      },
      fulfillment: {
        type: event.fulfillment_type,
        status: event.status,
        revision: event.revision,
        occurred_at: event.occurred_at,
        promise: event.fulfillment_promise,
      },
    },
    attempt_count: 0,
    created_at: now,
    updated_at: now,
    next_attempt_at: now,
    lease_until: null,
    sent_at: null,
    failure_code: null,
  }];
}

async function retrieveOrder(container: MedusaContainer, orderId: string): Promise<JsonRecord | undefined> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({ entity: "order", fields: ORDER_FIELDS, filters: { id: orderId } });
  return data[0] as JsonRecord | undefined;
}

async function persistOutbox(
  container: MedusaContainer,
  order: JsonRecord,
  outbox: NotificationEntry[],
): Promise<void> {
  const metadata = { ...record(order.metadata), [OUTBOX_KEY]: outbox };
  const orderModule = container.resolve(Modules.ORDER);
  await orderModule.updateOrders([{ id: order.id, metadata }]);
  order.metadata = metadata;
}

export async function ensureStorefrontOrderNotificationOutbox(
  container: MedusaContainer,
  orderId: string,
): Promise<void> {
  const order = await retrieveOrder(container, orderId);
  if (!order) return;
  const metadata = record(order.metadata);
  const current = entries(metadata[OUTBOX_KEY]);
  if (current.some((entry) => entry.id === `confirmation:${orderId}`)) return;
  const confirmation = confirmationEntry(order, new Date());
  if (confirmation) await persistOutbox(container, order, [...current, confirmation]);
}

function retryDelaySeconds(attempt: number): number {
  return Math.min(3600, 10 * 2 ** Math.min(attempt - 1, 8));
}

function failureCode(error: unknown): string {
  const code = error instanceof Error ? error.message : "";
  return /^[A-Za-z0-9_-]{1,80}$/.test(code) ? code.toLowerCase() : "notification_provider_failed";
}

async function send(container: MedusaContainer, order: JsonRecord, entry: NotificationEntry): Promise<void> {
  const metadata = record(order.metadata);
  const digest = metadata.storefront_confirmation_sha256;
  if (typeof digest !== "string") throw new Error("storefront_order_capability_missing");
  const data = {
    ...entry.data,
    order_access_url: accessUrl(order.id, digest),
  };
  const notificationModule = container.resolve(Modules.NOTIFICATION) as {
    createNotifications: (input: JsonRecord) => Promise<unknown>;
  };
  await notificationModule.createNotifications({
    idempotency_key: `storefront:${entry.id}`,
    to: entry.recipient,
    channel: "email",
    template: providerTemplate(entry),
    data,
    provider_data: {
      personalizations: [{
        to: [{ email: entry.recipient }],
        dynamic_template_data: data,
      }],
    },
  });
}

async function processOrder(container: MedusaContainer, orderId: string, now: Date): Promise<void> {
  const claim = await withStorefrontOrderHandoffLock(container, orderId, async () => {
    const order = await retrieveOrder(container, orderId);
    if (!order) return null;
    const metadata = record(order.metadata);
    let outbox = entries(metadata[OUTBOX_KEY]);
    let changed = false;
    const confirmationId = `confirmation:${order.id}`;
    if (!outbox.some((entry) => entry.id === confirmationId)) {
      const initial = confirmationEntry(order, now);
      if (initial) {
        outbox = [initial, ...outbox];
        changed = true;
      }
    }
    const candidate = outbox.find((entry) => entry.status === "pending" ||
      (entry.status === "retry_wait" && (!entry.next_attempt_at || new Date(entry.next_attempt_at) <= now)) ||
      (entry.status === "processing" && entry.lease_until && new Date(entry.lease_until) <= now));
    if (!candidate) {
      if (changed) await persistOutbox(container, order, outbox);
      return null;
    }
    const claimed = {
      ...candidate,
      status: "processing" as const,
      attempt_count: candidate.attempt_count + 1,
      updated_at: now.toISOString(),
      next_attempt_at: null,
      lease_until: new Date(now.getTime() + 5 * 60_000).toISOString(),
      failure_code: null,
    };
    outbox = outbox.map((entry) => entry.id === candidate.id ? claimed : entry);
    await persistOutbox(container, order, outbox);
    return { entry: claimed };
  });
  if (!claim) return;

  let failure: string | null = null;
  try {
    const order = await retrieveOrder(container, orderId);
    if (!order) throw new Error("storefront_order_not_found");
    await send(container, order, claim.entry);
  } catch (error) {
    failure = failureCode(error);
  }

  await withStorefrontOrderHandoffLock(container, orderId, async () => {
    const order = await retrieveOrder(container, orderId);
    if (!order) return;
    const outbox = entries(record(order.metadata)[OUTBOX_KEY]);
    const current = outbox.find((entry) => entry.id === claim.entry.id);
    if (!current || current.status !== "processing" || current.attempt_count !== claim.entry.attempt_count) return;
    const finished: NotificationEntry = failure
      ? {
          ...current,
          status: "retry_wait",
          updated_at: new Date().toISOString(),
          lease_until: null,
          next_attempt_at: new Date(Date.now() + retryDelaySeconds(current.attempt_count) * 1000).toISOString(),
          failure_code: failure,
        }
      : {
          ...current,
          status: "sent",
          updated_at: new Date().toISOString(),
          lease_until: null,
          next_attempt_at: null,
          sent_at: new Date().toISOString(),
          failure_code: null,
        };
    await persistOutbox(container, order, outbox.map((entry) => entry.id === current.id ? finished : entry));
  });
}

export async function retryStorefrontOrderNotifications(
  container: MedusaContainer,
  now = new Date(),
): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const take = 100;
  let skip = 0;
  while (true) {
    const { data } = await query.graph({
      entity: "order",
      fields: ["id", "metadata"],
      pagination: { take, skip },
    });
    const orders = data as { id: string }[];
    if (!orders.length) break;
    for (const order of orders) {
      try {
        await processOrder(container, order.id, now);
      } catch (error) {
        console.warn("Storefront notification remains retryable", {
          order_id: order.id,
          failure: failureCode(error),
        });
      }
    }
    if (orders.length < take) break;
    skip += orders.length;
  }
}
