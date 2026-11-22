import { describe, expect, it } from "vitest";

import { ApiError, type InventorySku, type TillBlockingReservation } from "./api";
import {
  basketConflict, conflictNotice, expiryNotice, heldExpiryNotice, heldSalesExplainer, heldTimeLeft,
  reservationReason, tillAvailability, tillClock,
} from "./till-reservations";

// 14:32 in Johannesburg (UTC+2).
const FREES = "2026-11-20T12:32:00Z";
const open: TillBlockingReservation = {
  location_id: "kram", location_name: "Kramerville", holder_kind: "basket", expires_at: FREES,
};

describe("reservation reason", () => {
  it("names the showroom and when an open sale frees the stock", () => {
    expect(tillClock(FREES)).toBe("14:32");
    expect(reservationReason(open)).toBe("Reserved in open sale at Kramerville · frees 14:32 unless sold");
  });

  it("leaves out the time when the hold has no expiry", () => {
    expect(reservationReason({ ...open, holder_kind: "held_sale", expires_at: null }))
      .toBe("Reserved in held sale at Kramerville");
    expect(reservationReason({ ...open, holder_kind: "invoice", expires_at: null }))
      .toBe("Reserved for an invoice at Kramerville");
  });
});

describe("till availability", () => {
  const row = {
    sku_id: "sofa",
    locations: [
      { location_id: "here", on_hand: 2 },
      { location_id: "warehouse", on_hand: 1 },
      { location_id: "archived", on_hand: 5 },
    ],
  } as InventorySku;
  const sellable = new Set(["here", "warehouse"]);
  const at = (reserved: number, inCart: number) => tillAvailability({
    row, sellableLocationIds: sellable, inCart,
    reservation: reserved ? { sku_id: "sofa", reserved_by_others: reserved, blocking: open } : undefined,
  });

  it("is limited by the company's unreserved stock at active locations, less the cart, not the floor", () => {
    expect(at(0, 0)).toEqual({ limit: 3, addable: 3, reason: null });
    expect(at(2, 0)).toEqual({ limit: 1, addable: 1, reason: null });
    expect(at(0, 2)).toEqual({ limit: 3, addable: 1, reason: null });
    expect(at(0, 3)).toEqual({ limit: 3, addable: 0, reason: null });
  });

  it("offers a SKU the showroom does not hold", () => {
    const warehouseOnly = { ...row, locations: [{ location_id: "warehouse", on_hand: 1 }] } as InventorySku;
    expect(tillAvailability({ row: warehouseOnly, sellableLocationIds: sellable, inCart: 0, reservation: undefined }))
      .toEqual({ limit: 1, addable: 1, reason: null });
  });

  it("explains a SKU that other sales' reservations block", () => {
    expect(at(3, 0)).toEqual({ limit: 0, addable: 0, reason: "Reserved in open sale at Kramerville · frees 14:32 unless sold" });
    expect(at(2, 1).reason).toContain("Kramerville");
  });
});

describe("expiry notice", () => {
  const expires = Date.parse(FREES);

  it("states the expiry and hold time while more than 15 minutes remain", () => {
    expect(expiryNotice(FREES, expires - 15 * 60_000 - 1, 4)).toEqual({
      kind: "info",
      title: "This sale expires at 14:32, 4 hours after the last change.",
      subtitle: "The items stay reserved until then; after that the sale is deleted and the stock released.",
    });
    expect(expiryNotice(FREES, expires - 60 * 60_000).title).toBe("This sale expires at 14:32.");
  });

  it("switches to a warning in the last 15 minutes", () => {
    expect(expiryNotice(FREES, expires - 15 * 60_000, 4)).toMatchObject({
      kind: "warning", title: "Expires at 14:32, in 15 minutes.",
    });
    expect(expiryNotice(FREES, expires - 30_000).title).toBe("Expires at 14:32, in 1 minute.");
    expect(expiryNotice(FREES, expires)).toMatchObject({ kind: "warning", title: "This sale expired at 14:32." });
  });
});

describe("basket conflicts", () => {
  const basket = {
    id: "b", location_id: "here", customer_id: null, note: null, pick_id: null, linked_pick_ids: {},
    lines: [], version: 3, updated_at: FREES, expires_at: null, expired_at: FREES,
    note_printed: null, note_internal: null, sales_staff_id: null, quote_id: null,
  };

  it("reads the server basket a conflict carries", () => {
    expect(basketConflict(new ApiError(409, "x", { code: "basket_expired", basket }))?.basket).toEqual(basket);
  });

  it("says which item was refused and why, or when the sale expired", () => {
    const name = (id: string) => (id === "sofa" ? "Oslo sofa" : undefined);
    expect(conflictNotice({ code: "stock_reserved", sku_id: "sofa", blocking: open, basket }, name)).toEqual({
      kind: "warning",
      title: "Oslo sofa was not added",
      subtitle: "Reserved in open sale at Kramerville · frees 14:32 unless sold.",
    });
    expect(conflictNotice({ code: "basket_expired", basket }, name).subtitle)
      .toBe("Your sale expired at 14:32. Its items were released. Add them again.");
    expect(conflictNotice({ code: "basket_version_conflict", basket }, name).title).toBe("Basket updated elsewhere");
  });
});

describe("held sale expiry", () => {
  const expires = Date.parse(FREES);
  const before = (minutes: number) => expires - minutes * 60_000;

  it("labels the time left and the showroom expiry time", () => {
    expect(heldTimeLeft(FREES, before(130)).label).toBe("2 h 10 min · 14:32");
    expect(heldTimeLeft(FREES, before(120)).label).toBe("2 h · 14:32");
    expect(heldTimeLeft(FREES, before(45)).label).toBe("45 min · 14:32");
    // Partial minutes round up, so the label never says 0 min before expiry.
    expect(heldTimeLeft(FREES, expires - 1_000)).toMatchObject({ label: "1 min · 14:32", minutes: 1 });
  });

  it("marks the last 15 minutes as urgent and the passed clock as expired", () => {
    expect(heldTimeLeft(FREES, before(15) - 1).urgent).toBe(false);
    expect(heldTimeLeft(FREES, before(15))).toMatchObject({ urgent: true, expired: false, duration: "15 min" });
    expect(heldTimeLeft(FREES, expires)).toEqual({
      expired: true, urgent: false, minutes: 0, duration: "", label: "Expired",
    });
  });

  it("warns on the selected sale only in its last 15 minutes", () => {
    expect(heldExpiryNotice(FREES, before(16))).toBeNull();
    expect(heldExpiryNotice(FREES, before(12))).toEqual({
      kind: "warning",
      title: "Expires at 14:32, in 12 minutes.",
      subtitle: "Resume it to keep the stock reserved. Otherwise it is deleted and the stock released.",
    });
    expect(heldExpiryNotice(FREES, before(0.5))?.title).toBe("Expires at 14:32, in 1 minute.");
    expect(heldExpiryNotice(FREES, expires)?.title).toBe("Expired at 14:32.");
  });

  it("explains the hold time, with or without the setting", () => {
    expect(heldSalesExplainer(3)).toBe(
      "Held sales keep their stock reserved for 3 hours from when they were held. " +
      "After that they are deleted and the stock released. Resuming a sale starts a new 3 hours.",
    );
    expect(heldSalesExplainer(1)).toContain("for 1 hour from");
    expect(heldSalesExplainer()).not.toMatch(/\d/);
  });

  it("shows the server's message when a resumed sale had expired", () => {
    expect(conflictNotice({ code: "held_sale_expired", message: "This held sale expired at 14:32." }, () => undefined))
      .toEqual({ kind: "warning", title: "Held sale expired", subtitle: "This held sale expired at 14:32." });
  });
});
