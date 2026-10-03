type RecordValue = Record<string, unknown>;

function record(value: unknown): RecordValue {
  return value && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {};
}

/** Refund credit lines change Medusa's net total. Display the immutable paid
 * handoff instead, without returning its customer/provider audit fields. */
export function paidOrderHistory(order: RecordValue): { total: number; items: Map<string, number> } | null {
  const payload = record(record(record(order.metadata).storefront_handoff_outbox).payload);
  const payment = record(payload.payment);
  const total = record(payload.totals).total_minor_zar;
  if (payload.external_order_id !== order.id || payload.currency_code !== "ZAR" ||
    typeof total !== "number" || !Number.isSafeInteger(total) || total < 0 ||
    payment.currency_code !== "ZAR" || payment.amount_minor_zar !== total) return null;
  const items = new Map<string, number>();
  for (const value of Array.isArray(payload.lines) ? payload.lines : []) {
    const line = record(value);
    if (typeof line.external_line_id === "string" && typeof line.total_minor_zar === "number" &&
      Number.isSafeInteger(line.total_minor_zar) && line.total_minor_zar >= 0) {
      items.set(line.external_line_id, line.total_minor_zar / 100);
    }
  }
  return { total: total / 100, items };
}

export function orderRefundStatus(order: RecordValue) {
  const rows = record(order.metadata).storefront_refunds;
  const currency = typeof order.currency_code === "string" ? order.currency_code.toUpperCase() : "ZAR";
  const items = (Array.isArray(rows) ? rows : []).flatMap((value) => {
    const row = record(value);
    if (typeof row.amount_minor !== "number" || !Number.isSafeInteger(row.amount_minor) || row.amount_minor <= 0 ||
      row.currency_code !== currency || typeof row.status !== "string" ||
      !["pending", "succeeded", "failed"].includes(row.status)) return [];
    return [{ amount_minor: row.amount_minor, currency_code: currency, status: row.status }];
  });
  const refunded = items.filter((item) => item.status === "succeeded").reduce((sum, item) => sum + item.amount_minor, 0);
  return items.length && Number.isSafeInteger(refunded) ? { refunded_amount_minor: refunded, items } : null;
}
