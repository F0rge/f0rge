import { describe, expect, it } from "vitest";
import { fulfillmentStatusLabel, storefrontOrderFulfillment } from "./order-fulfillment";

describe("storefrontOrderFulfillment", () => {
  it("prefers the durable fulfilment snapshot over Medusa payment status", () => {
    expect(storefrontOrderFulfillment({
      status: "completed",
      metadata: {
        storefront_checkout: { fulfillment_type: "delivery" },
        storefront_fulfillment_status: { fulfillment_type: "collection", status: "ready_for_collection" },
      },
    })).toEqual({ fulfillment_type: "collection", fulfillment_status: "ready_for_collection" });
  });

  it("defaults a paid order with no snapshot to confirmed", () => {
    expect(storefrontOrderFulfillment({
      metadata: { storefront_checkout: { fulfillment_type: "collection" } },
    })).toEqual({ fulfillment_type: "collection", fulfillment_status: "confirmed" });
    expect(fulfillmentStatusLabel("ready_for_collection")).toBe("Ready for collection");
  });
});
