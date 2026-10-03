type RecordValue = Record<string, unknown>;

function record(value: unknown): RecordValue {
  return value && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {};
}

export const FULFILLMENT_STATUS_LABELS: Record<string, string> = {
  confirmed: "Order confirmed",
  ready_for_delivery: "Preparing for delivery",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  ready_for_collection: "Ready for collection",
  collected: "Collected",
  cancelled: "Order cancelled",
};

const FULFILLMENT_STATUSES = new Set(Object.keys(FULFILLMENT_STATUS_LABELS));
const FULFILLMENT_TYPES = new Set(["delivery", "collection"]);

export function fulfillmentStatusLabel(status: string | null | undefined): string {
  return status && FULFILLMENT_STATUS_LABELS[status] ? FULFILLMENT_STATUS_LABELS[status] : "";
}

function knownType(value: unknown): string | null {
  return FULFILLMENT_TYPES.has(String(value)) ? String(value) : null;
}

function knownStatus(value: unknown): string | null {
  return FULFILLMENT_STATUSES.has(String(value)) ? String(value) : null;
}

/** Customer-visible fulfilment from Medusa metadata, never the raw payment status. */
export function storefrontOrderFulfillment(order: RecordValue): {
  fulfillment_type: string | null;
  fulfillment_status: string | null;
} {
  const metadata = record(order.metadata);
  const current = record(metadata.storefront_fulfillment_status);
  const snapshotType = knownType(current.fulfillment_type);
  const snapshotStatus = knownStatus(current.status);
  if (snapshotType || snapshotStatus) {
    return { fulfillment_type: snapshotType, fulfillment_status: snapshotStatus };
  }
  const checkoutType = knownType(record(metadata.storefront_checkout).fulfillment_type);
  if (checkoutType) {
    return { fulfillment_type: checkoutType, fulfillment_status: "confirmed" };
  }
  return { fulfillment_type: null, fulfillment_status: null };
}
