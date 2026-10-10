import type { MedusaContainer } from "@medusajs/framework/types";
import { BigNumber, ContainerRegistrationKeys, MathBN, Modules } from "@medusajs/framework/utils";
import { updateProductVariantsWorkflow } from "@medusajs/medusa/core-flows";
import { withCheckoutInventoryLock } from "./checkout-holds";
import { commitMadeToOrderCapacity } from "./made-to-order-capacity-store";
import { pendingCommitments } from "./ops-contract";

type JsonRecord = Record<string, any>;
type HandoffStatus = "pending" | "processing" | "retry_wait" | "stock_conflict" | "imported" | "failed";

type PaidOrderPayload = {
  company_id: string;
  channel: "storefront";
  external_order_id: string;
  external_payment_id: string;
  correlation_id: string;
  currency_code: "ZAR";
  customer: {
    external_id: string;
    name: string;
    email: string;
    phone: string;
    billing_address: string;
  };
  fulfillment: {
    type: "delivery" | "collection";
    reference: string;
    recipient: string;
    address: {
      address_1: string;
      address_2: string;
      city: string;
      province: string;
      postal_code: string;
      country_code: string;
    };
    fee_ex_minor_zar: number;
    fee_vat_minor_zar: number;
    fee_total_minor_zar: number;
  };
  lines: {
    external_line_id: string;
    source_sku_id: string;
    sku: string;
    title: string;
    quantity: number;
    unit_ex_minor_zar: number;
    unit_ex_remainder_minor_zar?: number;
    ex_minor_zar: number;
    vat_minor_zar: number;
    total_minor_zar: number;
    fulfillment_promise?: JsonRecord;
  }[];
  fulfillment_promise?: JsonRecord;
  totals: {
    subtotal_ex_minor_zar: number;
    tax_minor_zar: number;
    delivery_ex_minor_zar: number;
    delivery_tax_minor_zar: number;
    delivery_total_minor_zar: number;
    total_minor_zar: number;
  };
  payment: {
    provider: string;
    reference: string;
    captured_at: string;
    amount_minor_zar: number;
    currency_code: "ZAR";
  };
};

type StorefrontHandoffOutbox = {
  status: HandoffStatus;
  payload: PaidOrderPayload | null;
  correlation_id: string;
  created_at: string;
  updated_at: string;
  attempt_count: number;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  lease_until: string | null;
  failure_code: string | null;
};

const ROUND_HALF_UP = 4;
const ROUND_FLOOR = 3;

const ORDER_FIELDS = [
  "id", "display_id", "created_at", "email", "currency_code", "subtotal", "shipping_total", "shipping_tax_total", "tax_total", "total",
  "customer_id", "metadata",
  "items.id", "items.title", "items.quantity", "items.detail.quantity", "items.unit_price", "items.subtotal", "items.tax_total", "items.total",
  "items.metadata", "items.variant.sku", "items.variant.metadata",
  "shipping_methods.id", "shipping_methods.name", "shipping_methods.amount", "shipping_methods.subtotal", "shipping_methods.tax_total",
  "shipping_address.first_name", "shipping_address.last_name", "shipping_address.address_1", "shipping_address.address_2",
  "shipping_address.city", "shipping_address.province", "shipping_address.postal_code", "shipping_address.country_code", "shipping_address.phone",
  "billing_address.address_1", "billing_address.address_2", "billing_address.city", "billing_address.province", "billing_address.postal_code", "billing_address.country_code",
  "payment_collections.payments.id", "payment_collections.payments.provider_id", "payment_collections.payments.amount",
  "payment_collections.payments.currency_code", "payment_collections.payments.captured_at", "payment_collections.payments.data",
];

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" ? value as JsonRecord : {};
}

function string(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`missing_${field}`);
  return value.trim();
}

function majorAmount(value: unknown, field: string): ReturnType<typeof MathBN.convert> {
  let amount: ReturnType<typeof MathBN.convert>;
  if (value instanceof BigNumber) amount = MathBN.convert(value);
  else if (typeof value === "number" || typeof value === "string") amount = MathBN.convert(value);
  else {
    const source = record(value);
    const raw = record(source.raw_).value;
    const numeric = source.numeric_;
    if (typeof raw === "string" || typeof raw === "number") amount = MathBN.convert(raw);
    else if (typeof numeric === "number") amount = MathBN.convert(numeric);
    else throw new Error(`invalid_${field}`);
  }
  if (!amount.isFinite() || amount.isNegative()) throw new Error(`invalid_${field}`);
  return amount;
}

function minor(value: unknown, field: string): number {
  const result = MathBN.mult(majorAmount(value, field), 100).decimalPlaces(0, ROUND_HALF_UP).toNumber();
  if (!Number.isSafeInteger(result)) throw new Error(`invalid_${field}`);
  return result;
}

type MoneyComponent = { id: string; amount: ReturnType<typeof MathBN.convert>; maximum?: number };

/** Apportion aggregate rounded cents by largest remainder, bounded by gross for
 * tax allocations. Ties use stable line IDs, with delivery last.
 */
function allocateCents(components: MoneyComponent[], total: number): Map<string, number> {
  if (new Set(components.map((component) => component.id)).size !== components.length) {
    throw new Error("duplicate_money_component");
  }
  const shares = components.map((component) => {
    const cents = MathBN.mult(component.amount, 100);
    const floor = cents.integerValue(ROUND_FLOOR).toNumber();
    if (!Number.isSafeInteger(floor) || floor < 0 || (component.maximum !== undefined && floor > component.maximum)) {
      throw new Error("invalid_money_allocation");
    }
    return { ...component, floor, fraction: MathBN.sub(cents, floor) };
  });
  const remaining = total - shares.reduce((sum, share) => sum + share.floor, 0);
  const candidates = shares.filter((share) => !share.fraction.isZero() &&
    (share.maximum === undefined || share.floor < share.maximum))
    .sort((left, right) => right.fraction.comparedTo(left.fraction) ||
      Number(left.id === "delivery") - Number(right.id === "delivery") || left.id.localeCompare(right.id));
  if (remaining < 0 || remaining > candidates.length) throw new Error("invalid_money_allocation");
  const result = new Map(shares.map((share) => [share.id, share.floor]));
  for (const share of candidates.slice(0, remaining)) result.set(share.id, share.floor + 1);
  return result;
}

function zarCurrency(value: unknown, field: string): "ZAR" {
  if (typeof value !== "string" || value.trim().toUpperCase() !== "ZAR") throw new Error(`invalid_${field}`);
  return "ZAR";
}

function addressSnapshot(address: JsonRecord | null | undefined) {
  const source = record(address);
  return {
    address_1: string(source.address_1, "address_1"),
    address_2: typeof source.address_2 === "string" ? source.address_2 : "",
    city: string(source.city, "city"),
    province: string(source.province, "province"),
    postal_code: string(source.postal_code, "postal_code"),
    country_code: string(source.country_code, "country_code").toLowerCase(),
  };
}

export function retryDelaySeconds(attempt: number): number {
  const boundedAttempt = Math.max(1, Math.min(12, Math.floor(attempt)));
  return Math.min(1800, 15 * (2 ** (boundedAttempt - 1)));
}

export function classifyOpsResponse(statusCode: number, body: unknown): {
  status: HandoffStatus;
  failure_code: string | null;
  retry: boolean;
} {
  const response = record(body);
  if ((statusCode === 200 || statusCode === 201) && response.status === "imported") {
    return { status: "imported", failure_code: null, retry: false };
  }
  if (statusCode === 202 && response.status === "stock_conflict") {
    return { status: "stock_conflict", failure_code: "stock_unavailable", retry: false };
  }
  if (statusCode === 409) {
    return { status: "failed", failure_code: "idempotency_conflict", retry: false };
  }
  if (statusCode >= 500 || statusCode === 408 || statusCode === 429) {
    return { status: "retry_wait", failure_code: "ops_unavailable", retry: true };
  }
  if (statusCode >= 400) {
    return { status: "failed", failure_code: "ops_rejected_handoff", retry: false };
  }
  return { status: "retry_wait", failure_code: "ops_unavailable", retry: true };
}

export function buildPayload(order: JsonRecord): PaidOrderPayload {
  const companyId = string(process.env.FIRSTOUT_OPS_COMPANY_ID, "company_id");
  const orderId = string(order.id, "order_id");
  const shippingAddress = record(order.shipping_address);
  const billingAddress = record(order.billing_address);
  const checkout = record(record(order.metadata).storefront_checkout);
  const fulfillmentPromise = record(record(order.metadata).storefront_fulfillment_promise);
  const fulfillmentType = checkout.fulfillment_type === "collection" ? "collection" : "delivery";
  const items = Array.isArray(order.items) ? order.items as JsonRecord[] : [];
  if (!items.length) throw new Error("missing_items");
  const paymentCollections = Array.isArray(order.payment_collections) ? order.payment_collections as JsonRecord[] : [];
  const payments = paymentCollections.flatMap((collection) =>
    Array.isArray(collection.payments) ? collection.payments as JsonRecord[] : [],
  );
  const payment = payments.find((candidate) => candidate.captured_at) || payments[0];
  if (!payment) throw new Error("missing_captured_payment");
  const paymentData = record(payment.data);
  const providerReference = [paymentData.transaction_id, paymentData.reference, paymentData.provider_reference]
    .find((value) => typeof value === "string" && value.trim());
  const externalPaymentId = string(paymentData.provider_payment_id || payment.id, "payment_id");

  const total = minor(order.total, "order_total");
  const grossComponents = [
    ...items.map((item) => ({ id: string(item.id, "line_id"), amount: majorAmount(item.total ?? item.subtotal, "line_total") })),
    { id: "delivery", amount: majorAmount(order.shipping_total ?? 0, "shipping_total") },
  ];
  if (minor(new BigNumber(MathBN.sum(...grossComponents.map((part) => part.amount))), "gross_total") !== total) {
    throw new Error("order_total_mismatch");
  }
  if (minor(payment.amount, "payment_amount") !== total) throw new Error("payment_amount_mismatch");
  const grossById = allocateCents(grossComponents, total);
  const shippingTotal = grossById.get("delivery")!;
  const orderTaxTotal = minor(order.tax_total ?? 0, "order_tax_total");
  const itemTaxes = items.map((item) => majorAmount(item.tax_total ?? 0, "line_tax"));
  const rawShippingTax = order.shipping_tax_total ?? new BigNumber(MathBN.sub(
    majorAmount(order.tax_total ?? 0, "order_tax_total"), ...itemTaxes,
  ));
  const taxById = allocateCents([
    ...items.map((item, index) => ({
      id: string(item.id, "line_id"), maximum: grossById.get(item.id)!, amount: itemTaxes[index],
    })),
    { id: "delivery", maximum: shippingTotal, amount: majorAmount(rawShippingTax, "shipping_tax") },
  ], orderTaxTotal);

  const lines = items.map((item) => {
    const variant = record(item.variant);
    const metadata = record(variant.metadata);
    const sourceSkuId = string(metadata.source_sku_id, "source_sku_id");
    const quantity = Number(item.quantity);
    if (!Number.isSafeInteger(quantity) || quantity <= 0) throw new Error("invalid_quantity");
    const gross = grossById.get(string(item.id, "line_id"))!;
    const tax = taxById.get(string(item.id, "line_id"))!;
    if (tax > gross) throw new Error("invalid_line_tax");
    const ex = gross - tax;
    const unitRemainder = ex % quantity;
    const itemPromise = record(item.metadata).fulfillment_promise;
    const linePromise = itemPromise && Object.keys(itemPromise).length ? itemPromise : undefined;
    return {
      external_line_id: string(item.id, "line_id"),
      source_sku_id: sourceSkuId,
      sku: string(variant.sku, "sku"),
      title: string(item.title, "line_title"),
      quantity,
      unit_ex_minor_zar: Math.floor(ex / quantity),
      ...(unitRemainder ? { unit_ex_remainder_minor_zar: unitRemainder } : {}),
      ex_minor_zar: ex,
      vat_minor_zar: tax,
      total_minor_zar: gross,
      ...(linePromise ? { fulfillment_promise: linePromise } : {}),
    };
  });
  const promiseKind = fulfillmentPromise.kind;
  if ((promiseKind === "made_to_order" || promiseKind === "mixed") &&
    !lines.some((line) => line.fulfillment_promise?.kind === "made_to_order")) {
    throw new Error("missing_made_to_order_line_promise");
  }
  const shippingMethods = Array.isArray(order.shipping_methods) ? order.shipping_methods as JsonRecord[] : [];
  const shippingTax = taxById.get("delivery")!;
  const deliveryEx = shippingTotal - shippingTax;
  const deliveryTotal = deliveryEx + shippingTax;
  const subtotalEx = lines.reduce((total, line) => total + line.ex_minor_zar, 0);
  const capturedAt = payment.captured_at || order.created_at;
  const recipient = [shippingAddress.first_name, shippingAddress.last_name]
    .filter((value) => typeof value === "string" && value.trim()).join(" ");
  const email = string(order.email, "customer_email").toLocaleLowerCase("en-ZA");
  const billingParts = [
    billingAddress.address_1, billingAddress.address_2, billingAddress.city,
    billingAddress.province, billingAddress.postal_code,
  ].filter((value) => typeof value === "string" && value.trim());
  const fulfillment = shippingMethods[0];

  return {
    company_id: companyId,
    channel: "storefront",
    external_order_id: orderId,
    external_payment_id: externalPaymentId,
    correlation_id: `storefront:${orderId}`,
    currency_code: zarCurrency(order.currency_code, "currency_code"),
    customer: {
      external_id: typeof order.customer_id === "string" ? order.customer_id : orderId,
      name: recipient || email,
      email,
      phone: string(shippingAddress.phone, "customer_phone"),
      billing_address: billingParts.join(", "),
    },
    fulfillment: {
      type: fulfillmentType,
      reference: typeof fulfillment?.id === "string" ? fulfillment.id : orderId,
      recipient: recipient || email,
      address: addressSnapshot(shippingAddress),
      fee_ex_minor_zar: deliveryEx,
      fee_vat_minor_zar: shippingTax,
      fee_total_minor_zar: deliveryTotal,
    },
    lines,
    ...(Object.keys(fulfillmentPromise).length ? { fulfillment_promise: fulfillmentPromise } : {}),
    totals: {
      subtotal_ex_minor_zar: subtotalEx,
      tax_minor_zar: orderTaxTotal,
      delivery_ex_minor_zar: deliveryEx,
      delivery_tax_minor_zar: shippingTax,
      delivery_total_minor_zar: deliveryTotal,
      total_minor_zar: total,
    },
    payment: {
      provider: string(payment.provider_id, "payment_provider"),
      reference: typeof providerReference === "string" ? providerReference : string(payment.id, "payment_reference"),
      captured_at: new Date(capturedAt).toISOString(),
      amount_minor_zar: minor(payment.amount, "payment_amount"),
      currency_code: zarCurrency(payment.currency_code || order.currency_code, "payment_currency"),
    },
  };
}

async function retrieveOrder(container: MedusaContainer, orderId: string): Promise<JsonRecord | undefined> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({ entity: "order", fields: ORDER_FIELDS, filters: { id: orderId } });
  return data[0] as JsonRecord | undefined;
}

async function persistOutbox(
  container: MedusaContainer,
  order: JsonRecord,
  outbox: StorefrontHandoffOutbox,
): Promise<void> {
  const orderModule = container.resolve(Modules.ORDER);
  await orderModule.updateOrders([{
    id: string(order.id, "order_id"),
    metadata: { ...record(order.metadata), storefront_handoff_outbox: outbox },
  }]);
  order.metadata = { ...record(order.metadata), storefront_handoff_outbox: outbox };
}

function existingOutbox(order: JsonRecord): StorefrontHandoffOutbox | null {
  const value = record(order.metadata).storefront_handoff_outbox;
  if (!value || typeof value !== "object") return null;
  return value as StorefrontHandoffOutbox;
}

export async function ensureStorefrontOrderOutbox(
  container: MedusaContainer,
  orderId: string,
): Promise<StorefrontHandoffOutbox | null> {
  const order = await retrieveOrder(container, orderId);
  if (!order) return null;
  if (!record(order.metadata).storefront_confirmation_sha256) return null;
  const previous = existingOutbox(order);
  if (previous) {
    if (previous.payload || previous.status !== "failed" || previous.failure_code !== "paid_order_snapshot_invalid") {
      return previous;
    }
    // A snapshot that never completed contains no immutable payload yet. Let a
    // corrected serializer rebuild it from Medusa's retained paid-order facts.
    const repaired: StorefrontHandoffOutbox = {
      ...previous,
      status: "pending",
      payload: null,
      updated_at: new Date().toISOString(),
      next_attempt_at: new Date().toISOString(),
      lease_until: null,
      failure_code: null,
    };
    try {
      repaired.payload = buildPayload(order);
    } catch {
      return previous;
    }
    await persistOutbox(container, order, repaired);
    return repaired;
  }

  const now = new Date().toISOString();
  const base: StorefrontHandoffOutbox = {
    status: "pending",
    payload: null,
    correlation_id: `storefront:${orderId}`,
    created_at: now,
    updated_at: now,
    attempt_count: 0,
    last_attempt_at: null,
    next_attempt_at: now,
    lease_until: null,
    failure_code: null,
  };
  try {
    base.payload = buildPayload(order);
  } catch {
    base.status = "failed";
    base.failure_code = "paid_order_snapshot_invalid";
  }
  await persistOutbox(container, order, base);
  return base;
}

async function reservePaidCommitments(
  container: MedusaContainer,
  payload: PaidOrderPayload,
): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const commitmentsByVariant = new Map<string, { commitment_id: string; source_sku_id: string; quantity: number }[]>();
  for (const line of payload.lines) {
    // Resolve variants by their stable operational SKU identity, never by an order-supplied selector.
    const { data: variants } = await query.graph({
      entity: "product_variant",
      fields: ["id", "metadata"],
      filters: { sku: line.sku },
    });
    const variant = variants.find((row) => record(row.metadata).source_sku_id === line.source_sku_id) as JsonRecord | undefined;
    if (!variant) throw new Error("storefront_variant_mapping_missing");
    const commitments = commitmentsByVariant.get(variant.id) || [];
    commitments.push({
      commitment_id: `storefront:${payload.external_order_id}:${line.external_line_id}`,
      source_sku_id: line.source_sku_id,
      quantity: line.quantity,
    });
    commitmentsByVariant.set(variant.id, commitments);
  }

  for (const [variantId, additions] of commitmentsByVariant) {
    const { data: variants } = await query.graph({
      entity: "product_variant", fields: ["id", "metadata"], filters: { id: variantId },
    });
    const variant = variants[0] as JsonRecord | undefined;
    if (!variant) throw new Error("storefront_variant_mapping_missing");
    const metadata = record(variant.metadata);
    const old = pendingCommitments(metadata);
    const byId = new Map(old.map((entry) => [entry.commitment_id, entry]));
    for (const addition of additions) {
      const previous = byId.get(addition.commitment_id);
      if (previous && (previous.source_sku_id !== addition.source_sku_id || previous.quantity !== addition.quantity)) {
        throw new Error("storefront_commitment_conflict");
      }
      byId.set(addition.commitment_id, addition);
    }
    const pending = [...byId.values()];
    await updateProductVariantsWorkflow(container).run({
      input: { product_variants: [{ id: variantId, metadata: { ...metadata, pending_paid_commitments: pending } }] },
    });
  }
}

/** Caller must hold the shared inventory lock while updating variant commitments. */
export async function prepareStorefrontOrderHandoff(
  container: MedusaContainer,
  orderId: string,
): Promise<StorefrontHandoffOutbox | null> {
  return withStorefrontOrderHandoffLock(container, orderId, async () => {
    const outbox = await ensureStorefrontOrderOutbox(container, orderId);
    if (outbox?.payload && outbox.status !== "imported") {
      await reservePaidCommitments(container, outbox.payload);
      await commitMadeToOrderCapacity(container, orderId);
    }
    return outbox;
  });
}

export async function deliverStorefrontOrderOutbox(
  container: MedusaContainer,
  orderId: string,
  now: Date = new Date(),
): Promise<StorefrontHandoffOutbox | null> {
  // Source sync and checkout update the same variant metadata. Prepare under
  // their inventory lock before holding the order lock across the HTTP call.
  // Lock order is inventory -> order, matching the local payment callback.
  await withCheckoutInventoryLock(container, () => prepareStorefrontOrderHandoff(container, orderId));
  return withStorefrontOrderHandoffLock(container, orderId, async () => {
    const order = await retrieveOrder(container, orderId);
    if (!order) return null;
    const outbox = existingOutbox(order);
    if (!outbox || outbox.status === "imported" || outbox.status === "stock_conflict" || outbox.status === "failed") return outbox;
    if (!outbox.payload) return outbox;
    if (outbox.status === "retry_wait" && outbox.next_attempt_at && new Date(outbox.next_attempt_at) > now) return outbox;
    if (outbox.status === "processing" && outbox.lease_until && new Date(outbox.lease_until) > now) return outbox;

  const attempt = outbox.attempt_count + 1;
  const started: StorefrontHandoffOutbox = {
    ...outbox,
    status: "processing",
    attempt_count: attempt,
    last_attempt_at: now.toISOString(),
    updated_at: now.toISOString(),
    next_attempt_at: null,
    lease_until: new Date(now.getTime() + 30_000).toISOString(),
    failure_code: null,
  };
  await persistOutbox(container, order, started);

  const baseUrl = process.env.FIRSTOUT_OPS_URL;
  const token = process.env.FIRSTOUT_OPS_TOKEN;
  const companyId = process.env.FIRSTOUT_OPS_COMPANY_ID;
  if (!baseUrl || !token || !companyId) {
    return saveFailure(container, orderId, started, "ops_connection_unconfigured", true, now);
  }

  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/orders`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Ops-Company-ID": companyId,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(started.payload),
      signal: AbortSignal.timeout(15_000),
    });
    let body: unknown = null;
    try { body = await response.json(); } catch { /* status code is enough to retry safely */ }
    const result = classifyOpsResponse(response.status, body);
    const completed: StorefrontHandoffOutbox = {
      ...started,
      status: result.status,
      updated_at: new Date().toISOString(),
      lease_until: null,
      failure_code: result.failure_code,
      next_attempt_at: result.retry
        ? new Date(now.getTime() + retryDelaySeconds(attempt) * 1000).toISOString()
        : null,
    };
    const freshOrder = await retrieveOrder(container, orderId);
    if (freshOrder) await persistOutbox(container, freshOrder, completed);
    return completed;
  } catch {
    return saveFailure(container, orderId, started, "ops_unavailable", true, now);
  }
  });
}

/** Staff-authorized retry retains the immutable payload and never steals an active lease. */
export async function retryStorefrontOrderHandoff(container: MedusaContainer, orderId: string, replayImported = false): Promise<StorefrontHandoffOutbox | null> {
  await withStorefrontOrderHandoffLock(container, orderId, async () => {
    const order = await retrieveOrder(container, orderId);
    if (!order || !record(order.metadata).storefront_confirmation_sha256) throw new Error("paid_order_recovery_missing");
    const outbox = existingOutbox(order);
    if (!outbox || (outbox.status === "imported" && !replayImported)) return;
    if (outbox.status === "processing" && outbox.lease_until && Date.parse(outbox.lease_until) > Date.now()) {
      throw new Error("handoff_recovery_lease_active");
    }
    if (!outbox.payload) return; // Existing snapshot reconstruction validates the retained paid facts.
    await persistOutbox(container, order, { ...outbox, status: "pending", failure_code: null,
      next_attempt_at: null, lease_until: null, updated_at: new Date().toISOString() });
  });
  // Deliver performs the real capacity commitment and operational import under
  // inventory -> order locking, so release the previous order lock first.
  const result = await deliverStorefrontOrderOutbox(container, orderId);
  if (result?.status === "imported") {
    await withStorefrontOrderHandoffLock(container, orderId, async () => {
      const order = await retrieveOrder(container, orderId);
      if (!order || existingOutbox(order)?.status !== "imported") return;
      const metadata = record(order.metadata);
      if (record(metadata.storefront_capacity_exception).status !== "paid_exception") return;
      await container.resolve(Modules.ORDER).updateOrders([{ id: orderId, metadata: { ...metadata,
        storefront_capacity_exception: { ...record(metadata.storefront_capacity_exception), status: "resolved", resolved_at: new Date().toISOString() },
      } }]);
    });
  }
  return result;
}

type LockingModule = {
  execute<T>(key: string, operation: () => Promise<T>): Promise<T>;
};

export function withStorefrontOrderHandoffLock<T>(
  container: MedusaContainer,
  orderId: string,
  operation: () => Promise<T>,
): Promise<T> {
  const locking = container.resolve(Modules.LOCKING) as unknown as LockingModule;
  return locking.execute(`storefront:order-handoff:${orderId}`, operation);
}

async function saveFailure(
  container: MedusaContainer,
  orderId: string,
  current: StorefrontHandoffOutbox,
  failureCode: string,
  retry: boolean,
  now: Date,
): Promise<StorefrontHandoffOutbox> {
  const failed: StorefrontHandoffOutbox = {
    ...current,
    status: retry ? "retry_wait" : "failed",
    updated_at: new Date().toISOString(),
    failure_code: failureCode,
    lease_until: null,
    next_attempt_at: retry
      ? new Date(now.getTime() + retryDelaySeconds(current.attempt_count) * 1000).toISOString()
      : null,
  };
  const order = await retrieveOrder(container, orderId);
  if (order) await persistOutbox(container, order, failed);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  logger.warn(`Storefront order handoff ${failed.correlation_id} deferred: ${failureCode}`);
  return failed;
}

export function retryableStorefrontOutbox(value: unknown, now: Date): boolean {
  const outbox = record(value) as StorefrontHandoffOutbox;
  if (!outbox.payload || !["pending", "retry_wait", "processing"].includes(outbox.status)) return false;
  if (outbox.status === "retry_wait" && outbox.next_attempt_at && new Date(outbox.next_attempt_at) > now) return false;
  if (outbox.status === "processing" && outbox.lease_until && new Date(outbox.lease_until) > now) return false;
  return true;
}

export async function reconcileStorefrontHandoffs(
  container: MedusaContainer,
  acknowledgedCommitmentIds: string[],
): Promise<void> {
  const orderIds = new Set(
    acknowledgedCommitmentIds.flatMap((id) => {
      const match = /^storefront:([^:]+):/.exec(id);
      return match ? [match[1]] : [];
    }),
  );
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const orderModule = container.resolve(Modules.ORDER);
  for (const id of orderIds) {
    const { data } = await query.graph({ entity: "order", fields: ["id", "metadata"], filters: { id } });
    const order = data[0] as JsonRecord | undefined;
    if (!order) continue;
    const metadata = record(order.metadata);
    const outbox = existingOutbox(order);
    if (!outbox || outbox.status === "imported") continue;
    await orderModule.updateOrders([{
      id,
      metadata: {
        ...metadata,
        storefront_handoff_outbox: {
          ...outbox,
          status: "imported",
          failure_code: null,
          updated_at: new Date().toISOString(),
          next_attempt_at: null,
          lease_until: null,
        },
      },
    }]);
  }
}
