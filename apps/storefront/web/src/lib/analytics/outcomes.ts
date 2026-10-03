import { opaqueAnalyticsId, type AnalyticsCustomerType } from "./attribution";
import {
  commerceInsertId,
  sanitizeServerEvent,
  type PaymentProviderId,
  type PaymentReasonFamily,
  type StorefrontServerEvent,
} from "./commerce-events";
import { asMinorUnits, zarMinorUnits } from "./money";
import type { SanitizedAnalyticsEvent } from "./events";

export type PlannedServerOutcome = {
  event: SanitizedAnalyticsEvent;
  insertId: string;
};

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function orderKey(cartId: string | null, orderId: string | null): string | null {
  return opaqueAnalyticsId(cartId) || opaqueAnalyticsId(orderId);
}

/** Server-confirmed purchase and refund events. Browser confirmation refreshes reuse the same insert id. */
export function planConfirmationOutcomes(input: {
  cartId?: string | null;
  orderId?: string | null;
  customerType?: AnalyticsCustomerType | null;
  payload: unknown;
}): PlannedServerOutcome[] {
  const body = record(input.payload);
  const order = record(body?.order);
  if (body?.status !== "captured" || !order) return [];
  const analyticsOrderId = orderKey(input.cartId ?? null, input.orderId ?? null);
  const currency = typeof order.currency_code === "string" ? order.currency_code.toUpperCase() : "";
  if (!analyticsOrderId || currency !== "ZAR") return [];
  const valueMinor = asMinorUnits(order.captured_amount_minor) ?? zarMinorUnits(order.total);
  const items = Array.isArray(order.items) ? order.items : [];
  if (valueMinor === null) return [];

  const completed: StorefrontServerEvent = {
    name: "storefront_order_completed",
    properties: {
      analytics_order_id: analyticsOrderId,
      value_minor: valueMinor,
      item_count: Math.min(items.length, 99),
      currency: "ZAR",
      ...(input.customerType ? { customer_type: input.customerType } : {}),
    },
  };
  const planned: PlannedServerOutcome[] = [];
  const purchase = sanitizeServerEvent(completed);
  if (purchase) planned.push({ event: purchase, insertId: commerceInsertId(purchase.name, [analyticsOrderId]) });

  const refundStatus = record(order.refund_status);
  const refunds = Array.isArray(refundStatus?.items) ? refundStatus.items : [];
  refunds.forEach((item, index) => {
    const refund = record(item);
    if (!refund || refund.status !== "succeeded") return;
    const refundMinor = asMinorUnits(refund.amount_minor);
    if (refundMinor === null || refundMinor <= 0) return;
    const refundId = opaqueAnalyticsId(`rf_${index}_${refundMinor}`);
    if (!refundId) return;
    const event = sanitizeServerEvent({
      name: "storefront_order_refunded",
      properties: { analytics_order_id: analyticsOrderId, refund_id: refundId, refund_minor: refundMinor, currency: "ZAR" },
    });
    if (event) planned.push({ event, insertId: commerceInsertId(event.name, [analyticsOrderId, refundId]) });
  });
  return planned;
}

export function planPaymentFailure(input: {
  cartId: string | null;
  outcome: unknown;
  provider?: PaymentProviderId;
}): PlannedServerOutcome | null {
  const analyticsOrderId = opaqueAnalyticsId(input.cartId);
  const reason = input.outcome === "declined" || input.outcome === "cancelled" || input.outcome === "unknown"
    ? input.outcome as PaymentReasonFamily
    : null;
  if (!analyticsOrderId || !reason) return null;
  const event = sanitizeServerEvent({
    name: "storefront_payment_failed",
    properties: { analytics_order_id: analyticsOrderId, provider: input.provider || "test_simulator", reason_family: reason },
  });
  return event ? { event, insertId: commerceInsertId(event.name, [analyticsOrderId, reason]) } : null;
}

/** Same-process guard. Vendor dedupe uses the stable insert id when another instance also sends. */
export class OutcomeLedger {
  private readonly seen = new Set<string>();

  claim(insertId: string): boolean {
    if (this.seen.has(insertId)) return false;
    this.seen.add(insertId);
    if (this.seen.size > 5000) {
      const oldest = this.seen.values().next().value;
      if (oldest) this.seen.delete(oldest);
    }
    return true;
  }

  release(insertId: string): void {
    this.seen.delete(insertId);
  }
}
