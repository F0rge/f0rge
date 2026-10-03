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
  return FULFILLMENT_STATUS_LABELS[status || "confirmed"] || "Order confirmed";
}

/** Customer-visible fulfilment from Medusa metadata, never the raw payment status. */
export function storefrontOrderFulfillment(order: RecordValue): {
  fulfillment_type: string;
  fulfillment_status: string;
} {
  const metadata = record(order.metadata);
  const current = record(metadata.storefront_fulfillment_status);
  const checkout = record(metadata.storefront_checkout);
  const type = FULFILLMENT_TYPES.has(String(current.fulfillment_type))
    ? String(current.fulfillment_type)
    : FULFILLMENT_TYPES.has(String(checkout.fulfillment_type))
      ? String(checkout.fulfillment_type)
      : "delivery";
  const status = FULFILLMENT_STATUSES.has(String(current.status)) ? String(current.status) : "confirmed";
  return { fulfillment_type: type, fulfillment_status: status };
}
