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

  it("keeps checkout type and confirmed when a paid order has no status snapshot yet", () => {
    expect(storefrontOrderFulfillment({
      metadata: { storefront_checkout: { fulfillment_type: "collection" } },
    })).toEqual({ fulfillment_type: "collection", fulfillment_status: "confirmed" });
    expect(fulfillmentStatusLabel("confirmed")).toBe("Order confirmed");
    expect(fulfillmentStatusLabel("ready_for_collection")).toBe("Ready for collection");
  });

  it("does not invent confirmed or delivery when both snapshot and checkout type are missing", () => {
    expect(storefrontOrderFulfillment({
      status: "completed",
      metadata: { storefront_refunds: [{ status: "succeeded" }] },
    })).toEqual({ fulfillment_type: null, fulfillment_status: null });
    expect(fulfillmentStatusLabel(null)).toBe("");
    expect(fulfillmentStatusLabel("")).toBe("");
    expect(fulfillmentStatusLabel("unknown")).toBe("");
  });
});
