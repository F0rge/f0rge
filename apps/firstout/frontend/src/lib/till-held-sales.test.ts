import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type HeldSale } from "./api";
import {
  canKeepOriginalBasket, heldSaleRequest, isUncertainHeldResponse, readTillSession, saveTillSession,
  snapshotHeldSale, tillSessionKey, type PendingHeldOperation, type TillSession,
} from "./till-held-sales";

const held: HeldSale = {
  id: "sale-1", reference: "HS-1042", location_id: "showroom", customer_id: "customer",
  customer_name: "Example", held_by_name: "Staff", held_at: "2026-11-19T16:00:00Z",
  version: 3, note: "Collect this afternoon", estimated_total_inc_vat: "115.00",
  pick_id: null, linked_pick_ids: { service: "pick" },
  lines: [{
    sku_id: "service", sku_code: "SERVICE", sku_name: "Service", qty: 2,
    discount_percent: "12.50", estimated_total_inc_vat: "115.00",
  }],
};

afterEach(() => vi.unstubAllGlobals());

describe("held sale resume recovery", () => {
  it("stores the exact pending request and both baskets under the organisation and actor", () => {
    const data = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => data.get(key),
      setItem: (key: string, item: string) => data.set(key, item),
    });
    const destination = snapshotHeldSale(held);
    const cart = { ...destination, lines: [] };
    const staged: TillSession = {
      cart,
      pending: {
        kind: "resume", id: held.id, reference: held.reference, destination,
        request: { location_id: "showroom", operation_id: "stable-operation", version: 3, current: heldSaleRequest(destination) },
      },
    };
    const key = tillSessionKey("team", "staff");
    expect(saveTillSession(key, staged)).toBe(true);
    expect(readTillSession(key)).toEqual(staged);
    expect(readTillSession(tillSessionKey("team", "another-staff"))).toBeNull();
    expect(readTillSession(tillSessionKey("another-team", "staff"))).toBeNull();
    expect(destination.lines).toEqual([{ skuId: "service", qty: 2, discountPercent: 12.5 }]);
    expect(destination.linkedPickIds).toEqual({ service: "pick" });
    expect(destination.note).toBe("Collect this afternoon");
  });

  it("drops links from removed products without removing links from retained kits", () => {
    const cart = {
      ...snapshotHeldSale(held),
      linkedPickIds: { service: "valid-pick", removed: "stale-pick" },
    };
    expect(heldSaleRequest(cart).linked_pick_ids).toEqual({service: "valid-pick"});
  });

  it("fails closed when the browser cannot store the recovery copy", () => {
    vi.stubGlobal("sessionStorage", {
      setItem: () => { throw new DOMException("Storage disabled", "SecurityError"); },
    });
    expect(saveTillSession("session-key", { cart: snapshotHeldSale(held) })).toBe(false);
  });

  it("allows recovery of the original basket only after a receipt-first target conflict within the receipt window", () => {
    const operation: PendingHeldOperation = {
      kind: "resume", id: held.id, reference: held.reference, destination: snapshotHeldSale(held),
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
