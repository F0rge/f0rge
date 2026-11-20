import { describe, expect, it } from "vitest";

import { ApiError, type HeldSale } from "./api";
import {
  canKeepOriginalBasket, cartSnapshot, heldSaleRequest, isUncertainHeldResponse, type PendingHeldOperation,
} from "./till-held-sales";

const held: HeldSale = {
  id: "sale-1", reference: "HS-1042", location_id: "showroom", customer_id: "customer",
  customer_name: "Example", held_by_name: "Staff", held_at: "2026-11-19T16:00:00Z", expires_at: "2026-11-19T19:00:00Z",
  version: 3, note: "Collect this afternoon", estimated_total_inc_vat: "115.00",
  pick_id: null, linked_pick_ids: { service: "pick" },
  lines: [{
    sku_id: "service", sku_code: "SERVICE", sku_name: "Service", qty: 2,
    discount_percent: "12.50", estimated_total_inc_vat: "115.00",
  }],
};

describe("held sale resume recovery", () => {
  it("loads a held sale into the cart and holds the same contents again", () => {
    const destination = cartSnapshot(held);
    expect(destination.lines).toEqual([{ skuId: "service", qty: 2, discountPercent: 12.5 }]);
    expect(destination.linkedPickIds).toEqual({ service: "pick" });
    expect(destination.note).toBe("Collect this afternoon");
    expect(heldSaleRequest(destination)).toMatchObject({
      location_id: "showroom", customer_id: "customer", note: "Collect this afternoon",
      linked_pick_ids: { service: "pick" }, lines: [{ sku_id: "service", qty: 2, discount_percent: 12.5 }],
    });
  });

  it("drops links from removed products without removing links from retained kits", () => {
    const cart = {
      ...cartSnapshot(held),
      linkedPickIds: { service: "valid-pick", removed: "stale-pick" },
    };
    expect(heldSaleRequest(cart).linked_pick_ids).toEqual({service: "valid-pick"});
  });

  it("allows recovery of the original basket only after a receipt-first target conflict within the receipt window", () => {
    const operation: PendingHeldOperation = {
      kind: "resume", id: held.id, reference: held.reference, destination: cartSnapshot(held),
      request: { location_id: "showroom", operation_id: "stable-operation", version: 3 },
      startedAt: 1_000,
    };
    const targetChanged = new ApiError(409, "Sale changed", {code: "held_resume_target_changed"});
    expect(canKeepOriginalBasket(targetChanged, operation, 2_000)).toBe(true);
    expect(canKeepOriginalBasket(targetChanged, operation, 500)).toBe(false);
    expect(canKeepOriginalBasket(targetChanged, operation, 30 * 24 * 60 * 60 * 1000)).toBe(false);
    expect(canKeepOriginalBasket(new ApiError(409, "Other conflict"), operation, 2_000)).toBe(false);
  });

  it("treats transient or malformed responses as uncertain and validation conflicts as definite", () => {
    expect(isUncertainHeldResponse(new ApiError(0, "Offline"))).toBe(true);
    expect(isUncertainHeldResponse(new ApiError(504, "Timed out"))).toBe(true);
    expect(isUncertainHeldResponse(new SyntaxError("Malformed response"))).toBe(true);
    expect(isUncertainHeldResponse(new ApiError(409, "Already changed"))).toBe(false);
  });
});
