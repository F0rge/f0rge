type JsonRecord = Record<string, unknown>;

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function number(value: unknown): number | null {
  const result = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
  return Number.isSafeInteger(result) && result >= 0 ? result : null;
}

function major(valueMinor: number): number {
  return Number((valueMinor / 100).toFixed(2));
}

/**
 * Projects the original accepted/captured order values from the immutable
 * handoff outbox. Medusa Order totals can become net of refund credit lines;
 * pre-discount `original_total` is not a substitute for the amount captured.
 */
export function storefrontOrderHistory(order: JsonRecord): {
  subtotal: unknown;
  shipping_total: unknown;
  tax_total: unknown;
  total: unknown;
  captured_amount_minor: number | null;
  captured_at: string | null;
  itemTotals: Map<string, number>;
} {
  const metadata = record(order.metadata);
  const handoff = record(metadata.storefront_handoff_outbox);
  const payload = record(handoff.payload);
  const totals = record(payload.totals);
  const payment = record(payload.payment);
  const subtotal = number(totals.subtotal_ex_minor_zar);
  const tax = number(totals.tax_minor_zar);
  const shipping = number(totals.delivery_total_minor_zar);
  const shippingEx = number(totals.delivery_ex_minor_zar);
  const total = number(totals.total_minor_zar);
  const captureAmount = number(payment.amount_minor_zar);
  const itemTotals = new Map<string, number>();
  let lineTotalMinor = 0;
  let linesValid = Array.isArray(payload.lines) && payload.lines.length > 0;
  if (Array.isArray(payload.lines)) {
    for (const item of payload.lines) {
      const line = record(item);
      const id = line.external_line_id;
      const amount = number(line.total_minor_zar);
      if (typeof id === "string" && amount !== null && !itemTotals.has(id)) {
        itemTotals.set(id, major(amount));
        lineTotalMinor += amount;
      } else {
        linesValid = false;
        itemTotals.clear();
      }
    }
  }
  if (!linesValid) itemTotals.clear();

  const orderId = order.id;
  const itemIds = new Set((Array.isArray(order.items) ? order.items : [])
    .map((item) => record(item).id).filter((id): id is string => typeof id === "string"));
  const linesMatchOrder = itemTotals.size > 0 && itemTotals.size === itemIds.size &&
    [...itemTotals.keys()].every((id) => itemIds.has(id));
  const hasOriginalTotals = payload.external_order_id === orderId && payload.currency_code === "ZAR" && payment.currency_code === "ZAR" &&
    subtotal !== null && tax !== null && shipping !== null && total !== null && captureAmount === total &&
    shippingEx !== null && subtotal + tax + shippingEx === total && lineTotalMinor + shipping === total && linesMatchOrder;
  if (!hasOriginalTotals) itemTotals.clear();
  return {
    subtotal: hasOriginalTotals ? major(subtotal) : order.subtotal,
    shipping_total: hasOriginalTotals ? major(shipping) : order.shipping_total,
    tax_total: hasOriginalTotals ? major(tax) : order.tax_total,
    total: hasOriginalTotals ? major(total) : order.total,
    captured_amount_minor: hasOriginalTotals ? captureAmount : null,
    captured_at: hasOriginalTotals && typeof payment.captured_at === "string" && Number.isFinite(Date.parse(payment.captured_at))
      ? payment.captured_at : null,
    itemTotals,
  };
}
